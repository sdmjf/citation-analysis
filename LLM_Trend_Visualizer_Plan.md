# LLM Research Trend Visualizer — 项目计划书

> **目标**：基于 ACL Anthology 数据，构建一个面向研究者的 LLM 论文趋势可视化网站，
> 通过 embedding 聚类 + LLM 自动命名，展示 2018 年以来各研究方向的影响力变化。

---

## 项目结构

```
llm-trend-viz/
├── data/                          # 原始数据与处理后数据
│   ├── raw/                       # ACL Anthology 原始 JSON
│   └── processed/                 # 清洗后数据、embedding、聚类结果
├── pipeline/                      # 数据处理 pipeline（Python）
│   ├── 01_fetch_data.py           # 数据获取与清洗
│   ├── 02_filter_llm.py           # LLM 相关论文过滤
│   ├── 03_embed.py                # Embedding 生成
│   ├── 04_cluster.py              # 聚类
│   ├── 05_name_clusters.py        # LLM 自动命名
│   ├── 06_compute_metrics.py      # 影响力指标计算
│   └── 07_export_api_data.py      # 导出前端所需 JSON
├── backend/                       # FastAPI 后端
│   ├── main.py
│   ├── routers/
│   │   ├── trends.py
│   │   ├── papers.py
│   │   └── clusters.py
│   └── database.py                # SQLite 操作
├── frontend/                      # React 前端
│   ├── src/
│   │   ├── components/
│   │   │   ├── BubbleChart.jsx    # 主气泡图
│   │   │   ├── StreamGraph.jsx    # 河流图
│   │   │   ├── Heatmap.jsx        # 热力图
│   │   │   ├── DetailPanel.jsx    # 侧边详情面板
│   │   │   ├── PaperList.jsx      # 论文列表
│   │   │   └── TrendingList.jsx   # 新兴方向榜
│   │   ├── pages/
│   │   │   ├── Home.jsx
│   │   │   └── ClusterDetail.jsx
│   │   └── App.jsx
│   └── package.json
└── requirements.txt               # Python 依赖
```

---

## 技术栈

| 层 | 技术选型 |
|---|---|
| 数据处理 | Python 3.10+, pandas, sentence-transformers (SPECTER2), umap-learn, hdbscan |
| Citation 补充 | Semantic Scholar API (免费，使用 `/paper/batch` 批量接口，API Key 通过环境变量 `SEMANTIC_SCHOLAR_API_KEY` 注入) |
| LLM 命名 | Anthropic Claude API (`claude-sonnet-4-6`) |
| 后端 | FastAPI + SQLite (aiosqlite) |
| 前端 | React 18 + Vite + ECharts 5 + TailwindCSS |
| 部署 | 本地运行即可，前后端分离 |

---

## STEP 1 — 数据获取与清洗

**文件：`pipeline/01_fetch_data.py`**

### 任务
1. 下载 ACL Anthology 完整数据集（JSON 格式） 以及semantic scholar上的顶会NLP论文
2. 过滤 2018 年之后的论文
3. 尽量保持所有 Venue（ACL, EMNLP, NAACL, EACL, COLING, Finding...），以及semantic scholar上的ICLR, NeuroIPS, ICML这些顶级会议的NLP论文
4. 保留字段：`paper_id, title, abstract, year, month, venue, authors, url`
5. 去除 abstract 为空的论文

### 实现细节

```python
# ACL Anthology 提供完整 JSON dump，直接下载
ACL_URL = "https://aclanthology.org/anthology.json.gz"

TARGET_VENUES = ["ACL", "EMNLP", "NAACL", "EACL", "COLING", "TACL",
                 "Findings of ACL", "Findings of EMNLP", "Findings of NAACL"]

# venue_weight 定义：反映各会议的学术影响力层级
VENUE_WEIGHTS = {
    "ACL": 1.0,
    "EMNLP": 1.0,
    "NAACL": 0.9,
    "TACL": 1.0,          # 期刊，影响力高
    "ICLR": 1.0,
    "NeurIPS": 1.0,
    "ICML": 1.0,
    "EACL": 0.8,
    "COLING": 0.8,
    "Findings of ACL": 0.7,
    "Findings of EMNLP": 0.7,
    "Findings of NAACL": 0.7,
}
DEFAULT_VENUE_WEIGHT = 0.6  # 其他 venue

# 输出：data/processed/papers_clean.csv
# 字段：paper_id, title, abstract, year, quarter, venue, venue_weight, authors, url
```

**注意**：
- ACL Anthology JSON 中 venue 信息在 `booktitle` 或 `venue` 字段，需要做模糊匹配
- quarter 字段由 month 推算：1-3月=Q1, 4-6月=Q2, 7-9月=Q3, 10-12月=Q4
- 若 month 为空，默认 Q3（大多数 ACL 主会在夏季）

---

## STEP 2 — Citation 数据获取

**文件：`pipeline/01_fetch_data.py`（追加到 Step 1 脚本中）**

### 任务
通过 Semantic Scholar API 批量获取 citation count，用 paper title 做匹配。

```python
import requests
import time
import os

SEMANTIC_SCHOLAR_BATCH_API = "https://api.semanticscholar.org/graph/v1/paper/batch"
API_KEY = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")

def get_citations_batch(paper_ids: list[str]) -> dict:
    """
    使用批量接口一次获取最多 500 篇论文的 citation count。
    paper_ids 格式：["ACL:2022.acl-long.1", "DOI:10.xxx", ...]
    优先用 ACL Anthology 的 paper_id，格式为 "ACL:<id>"。
    """
    headers = {"x-api-key": API_KEY} if API_KEY else {}
    resp = requests.post(
        SEMANTIC_SCHOLAR_BATCH_API,
        params={"fields": "citationCount,externalIds"},
        json={"ids": paper_ids},
        headers=headers
    )
    resp.raise_for_status()
    return {item["paperId"]: item.get("citationCount", 0) for item in resp.json() if item}

# 批量处理：每批 500 篇，约 25,000 篇只需 50 次请求（~2 分钟）
# 输出新增字段：citation_count
# 保存到：data/processed/papers_with_citations.csv
```

**注意**：
- 批量接口每次最多 500 条，比逐条搜索效率提升约 10 倍
- 用 ACL paper_id（格式 `ACL:<id>`）匹配，避免标题搜索的误匹配
- 申请免费 API Key（无需审核，通过 `SEMANTIC_SCHOLAR_API_KEY` 环境变量注入）可提高速率上限
- 用 tqdm 显示进度，支持断点续传（已获取的跳过）

---

## STEP 3 — LLM 相关论文过滤

**文件：`pipeline/02_filter_llm.py`**

### 任务
从所有 ACL 论文中过滤出与 LLM/NLP 核心方向相关的论文。

### 方法
使用**关键词过滤**（召回） + **embedding 相似度**（精排），两阶段过滤：

```python
# 第一阶段：关键词过滤（宽泛，高召回）
LLM_KEYWORDS = [
    "language model", "large language model", "LLM", "GPT", "BERT", "transformer",
    "pre-train", "pretrain", "fine-tun", "instruction tun", "RLHF", "alignment",
    "prompt", "in-context learning", "few-shot", "zero-shot", "chain-of-thought",
    "reasoning", "generation", "text generation", "dialogue", "summarization",
    "translation", "question answering", "information extraction", "NER",
    "sentiment", "embeddings", "encoder", "decoder", "attention", "tokeniz",
    "hallucination", "RAG", "retrieval augmented", "agent", "tool use",
    "multimodal", "vision language", "speech language"
]

# 在 title + abstract 中匹配（小写，部分匹配）
# 预期过滤后保留约 60-70% 的论文

# 第二阶段：不做 embedding 过滤，直接进入聚类
# 因为 HDBSCAN 会自动把非 LLM 的 cluster 孤立出来
# 在聚类后命名阶段手动过滤掉明显不相关的 cluster 即可

# 输出：data/processed/papers_filtered.csv
```

---

## STEP 4 — Embedding 生成 （这一步可以直接access colab，因为我有colab的GPU hours）

**文件：`pipeline/03_embed.py`**

### 任务
使用 SPECTER2 模型为每篇论文生成 768 维向量。

```python
from sentence_transformers import SentenceTransformer

# 使用 SPECTER2（学术论文专用，效果最佳）
model = SentenceTransformer("allenai/specter2_base")

def encode_papers(df):
    # 拼接 title + abstract 作为输入
    texts = (df["title"] + " [SEP] " + df["abstract"]).tolist()
    # batch_size=32, 约 10k 篇论文需要 ~10 分钟（CPU）或 ~2 分钟（GPU）
    embeddings = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=True,
        convert_to_numpy=True
    )
    return embeddings

# 保存：data/processed/embeddings.npy（numpy 格式）
# 同时保存 paper_ids 对应关系：data/processed/embedding_ids.csv
```

**注意**：
- 如有 GPU，自动使用 CUDA
- 若无法安装 SPECTER2，备选方案：`sentence-transformers/all-mpnet-base-v2`
- 分批保存，支持断点续传

---

## STEP 5 — 聚类（与第四步一样可以直接在colab中运行）

**文件：`pipeline/04_cluster.py`**

### 任务
使用 UMAP 降维 + HDBSCAN 聚类，生成研究方向簇。

```python
import umap
import hdbscan
import numpy as np

def cluster_papers(embeddings):
    # Step 1: UMAP 降维（高维 → 10 维，用于聚类）
    reducer = umap.UMAP(
        n_components=10,
        n_neighbors=15,
        min_dist=0.0,
        metric="cosine",
        random_state=42
    )
    reduced = reducer.fit_transform(embeddings)

    # Step 2: HDBSCAN 聚类
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=30,       # 一个研究方向至少 30 篇论文
        min_samples=10,
        metric="euclidean",
        cluster_selection_method="eom"
    )
    labels = clusterer.fit_predict(reduced)

    # Step 3: UMAP 降维（10 维 → 2 维，用于前端可视化散点图）
    reducer_2d = umap.UMAP(
        n_components=2,
        n_neighbors=15,
        min_dist=0.1,
        metric="cosine",
        random_state=42
    )
    coords_2d = reducer_2d.fit_transform(embeddings)

    return labels, coords_2d

# 输出：
# data/processed/cluster_labels.npy   （每篇论文的 cluster id，-1 表示噪声）
# data/processed/umap_2d.npy          （2D 坐标，用于散点图）
```

**预期结果**：
- 总 cluster 数约 40-80 个（建议先以 `min_cluster_size=50` 开始，避免过多细碎 cluster）
- label=-1 的噪声论文约占 10-15%，忽略即可
- min_cluster_size 可根据实际结果调整（30-80 之间）

---

## STEP 6 — LLM 自动命名（这个步骤，我也可以调用openrouter，如果ANTHROPIC_API_KEY无法调用，你可以直接找我索要openrouter的key，然后openrouter需要使用的具体模型需要我提供给你）

**文件：`pipeline/05_name_clusters.py`**

### 任务
为每个 cluster 生成研究方向名称和描述，使用 Claude API。

```python
import anthropic
import json

client = anthropic.Anthropic()  # 自动读取 ANTHROPIC_API_KEY 环境变量

NAMING_PROMPT = """你是一位 NLP/AI 领域的专家研究员。
以下是同一研究方向的论文标题（按引用数从高到低排列）：

{titles}

请完成以下任务：
1. 用 3-6 个词给出这个研究方向的**名称**（中英文均可，优先英文）
2. 用 1-2 句话描述这个研究方向的核心内容
3. 判断这个方向是否属于 LLM/NLP 研究（是/否）

返回严格的 JSON 格式，不要有其他内容：
{{
  "name": "研究方向名称",
  "description": "一两句话描述",
  "is_nlp_related": true/false
}}"""

def name_cluster(cluster_papers_df, top_k=25):
    # 取 citation 最高的 top_k 篇论文
    top_papers = cluster_papers_df.nlargest(top_k, "citation_count")
    titles = "\n".join([f"- {t}" for t in top_papers["title"].tolist()])

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        messages=[{"role": "user", "content": NAMING_PROMPT.format(titles=titles)}]
    )

    result = json.loads(message.content[0].text)
    return result

# 对每个 cluster 调用一次 API
# 输出：data/processed/cluster_names.json
# 格式：{cluster_id: {name, description, is_nlp_related}}
```

**注意**：
- 调用完成后，手动检查 `is_nlp_related=false` 的 cluster，将其标记为忽略
- 预计 API 调用费用极低（约 50-80 个 cluster × 300 tokens = < $0.5）

---

## STEP 7 — 影响力指标计算

**文件：`pipeline/06_compute_metrics.py`**

### 任务
计算每个 cluster 在每个时间段（按季度）的各项指标。

```python
import pandas as pd
import numpy as np

def compute_venue_weighted_citations(df):
    """venue 加权后的 citation 分数"""
    return df["citation_count"] * df["venue_weight"]

def compute_recency_decay(year, current_year=2026):
    """时间衰减：越新的论文权重越高"""
    return np.exp(-0.2 * (current_year - year))

def compute_cluster_quarterly_metrics(papers_df, cluster_labels):
    """计算每个 cluster 每季度的指标"""
    papers_df["cluster_id"] = cluster_labels
    papers_df["period"] = papers_df["year"].astype(str) + "-" + papers_df["quarter"]

    results = []
    for (cluster_id, period), group in papers_df.groupby(["cluster_id", "period"]):
        if cluster_id == -1:
            continue
        results.append({
            "cluster_id": cluster_id,
            "period": period,             # e.g., "2023-Q2"
            "year": int(period[:4]),
            "quarter": period[5:],
            "paper_count": len(group),
            "total_citations": group["citation_count"].sum(),
            "weighted_citations": compute_venue_weighted_citations(group).sum(),
            "avg_citations": group["citation_count"].mean(),
            "top_paper_id": group.nlargest(1, "citation_count")["paper_id"].values[0],
        })

    return pd.DataFrame(results)

def compute_trend_score(metrics_df):
    """
    Trend Score = 最近两个季度加权引用 / 历史平均加权引用
    > 1.5 → Rising 🔥, 0.8-1.5 → Stable, < 0.8 → Declining
    """
    # 按 cluster_id 分组计算
    # ...（具体实现见代码）
    pass

# 输出：
# data/processed/quarterly_metrics.csv   （每 cluster 每季度指标）
# data/processed/cluster_summary.json   （每 cluster 汇总信息，含 trend_score）
```

---

## STEP 8 — 导出前端数据

**文件：`pipeline/07_export_api_data.py`**

### 任务
将所有处理结果整合，导出前端直接使用的 JSON 文件。

```python
# 输出文件列表（放到 backend/static/ 或前端 public/ 下）

# 1. clusters.json — 所有研究方向信息
{
  "clusters": [
    {
      "id": 3,
      "name": "Instruction Tuning & Alignment",
      "description": "研究如何通过指令微调和人类反馈对齐语言模型...",
      "trend_score": 2.3,
      "trend_label": "rising",          // rising / stable / declining
      "total_citations": 45230,
      "paper_count": 312,
      "top_papers": [                   // Top 10 代表论文
        {
          "paper_id": "2022.acl-long.1",
          "title": "...",
          "year": 2022,
          "citation_count": 8920,
          "url": "https://aclanthology.org/..."
        }
      ],
      "related_clusters": [5, 12, 7],  // embedding 距离最近的 cluster ids
      "top_venues": ["ACL", "EMNLP"],
      "peak_period": "2023-Q2"
    }
  ]
}

# 2. timeline.json — 按季度的时间序列数据（用于气泡图/河流图）
{
  "periods": ["2018-Q1", "2018-Q2", ..., "2024-Q4"],
  "series": {
    "3": [                             // cluster_id → 每季度数据数组
      {"period": "2018-Q1", "paper_count": 5, "weighted_citations": 230},
      ...
    ]
  }
}

# 3. papers.json — 所有论文（用于散点图和搜索）
{
  "papers": [
    {
      "paper_id": "...",
      "title": "...",
      "year": 2023,
      "quarter": "Q2",
      "venue": "ACL",
      "cluster_id": 3,
      "citation_count": 150,
      "x": 0.23,     // UMAP 2D 坐标（用于散点图）
      "y": -1.45,
      "url": "..."
    }
  ]
}
```

---

## STEP 9 — 后端 API

**文件：`backend/main.py`**

### 任务
构建 FastAPI 服务，提供数据接口。

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import json

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时加载 JSON 到内存（clusters + timeline 约 10MB，papers 按需分页）
    app.state.clusters = json.load(open("static/clusters.json"))
    app.state.timeline = json.load(open("static/timeline.json"))
    # papers.json 不整体加载，改为按 cluster_id/year 分片文件按需读取
    yield
    # 清理（如有数据库连接等资源在此释放）

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_methods=["*"],
    allow_headers=["*"]
)

# API 端点
@app.get("/api/clusters")             # 所有 cluster 列表（含 trend_score）
@app.get("/api/clusters/{id}")        # 单个 cluster 详情
@app.get("/api/timeline")             # 时间序列数据
@app.get("/api/papers")               # 论文列表（支持 cluster_id, year, keyword 过滤）
@app.get("/api/trending")             # trend_score 最高的 10 个 cluster
@app.get("/api/search")               # 全文搜索（title/abstract）
```

**运行方式**：
```bash
cd backend
uvicorn main:app --reload --port 8000
```

---

## STEP 10 — 前端可视化

### 整体布局

```
┌─────────────────────────────────────────────────────────┐
│  Header: LLM Research Trends  |  时间范围筛选 | 搜索框  │
├─────────────────────┬───────────────────────────────────┤
│                     │                                   │
│   主视图区域        │  侧边详情面板（点击后展开）        │
│   (可切换)          │                                   │
│   ① 气泡图          │  - 方向名称 + 描述                │
│   ② 河流图          │  - 影响力折线图                   │
│   ③ 热力图          │  - Top-10 论文列表                │
│   ④ 散点图          │  - 相关研究方向                   │
│                     │  - 活跃 Venue 统计                │
├─────────────────────┴───────────────────────────────────┤
│  底部: 新兴方向榜 (Trending 🔥)  |  总体统计数字        │
└─────────────────────────────────────────────────────────┘
```

### 组件实现

**① 气泡图（BubbleChart.jsx）** — 主视图，使用 ECharts scatter

```jsx
// X轴：时间（按季度）
// Y轴：研究方向（按总 citation 排序，显示 Top 20）
// 气泡大小：该季度加权 citation 总量
// 气泡颜色：
//   - 红色 (#FF6B6B)：trend_score > 1.5（Rising）
//   - 蓝色 (#4ECDC4)：trend_score 0.8-1.5（Stable）
//   - 灰色 (#95A5A6)：trend_score < 0.8（Declining）
// 交互：点击气泡 → 打开侧边详情面板
```

**② 河流图（StreamGraph.jsx）** — 使用 ECharts ThemeRiver

```jsx
// 展示 Top 15 研究方向随时间的论文数量占比变化
// 适合看整体格局的演变（哪些方向崛起，哪些衰退）
```

**③ 热力图（Heatmap.jsx）** — 使用 ECharts heatmap

```jsx
// X轴：年份（2018-2024）
// Y轴：研究方向（Top 30）
// 颜色深浅：该年该方向论文数量
// 用于快速扫描哪个方向在哪年最活跃
```

**④ 散点图（ScatterPlot.jsx）** — 使用 ECharts scatter（UMAP 2D）

```jsx
// 使用 UMAP 2D 坐标展示所有论文在语义空间中的分布
// 颜色：按 cluster 上色
// 点击论文点：显示论文详情
// 适合探索相邻方向、发现边界论文
//
// ⚠️ 注意：25,000 个点需开启 ECharts large 模式
// series: [{ type: "scatter", large: true, largeThreshold: 2000, ... }]
// large 模式下 tooltip 交互受限，点击事件需用 click handler 替代 hover
```

### 侧边详情面板（DetailPanel.jsx）

```jsx
// 包含：
// - 方向名称 + trend badge（🔥 Rising / Stable / Declining）
// - 一句话描述
// - 影响力趋势折线图（ECharts line）
// - Top 10 论文（含 ACL Anthology 跳转链接）
// - 相关方向 tags（点击可切换）
// - 活跃 Venue 饼图
```

---

## STEP 11 — 更新机制

**文件：`pipeline/update.sh`**

```bash
#!/bin/bash
# 每月运行一次

echo "Checking for ACL Anthology updates..."
python pipeline/01_fetch_data.py --incremental     # 只获取新增论文
python pipeline/06_compute_metrics.py              # 重新计算指标
python pipeline/07_export_api_data.py              # 重新导出 JSON

# 如果新增论文 > 总量 5%，触发重新聚类
NEW_COUNT=$(cat data/processed/update_stats.json | python -c "import sys,json; print(json.load(sys.stdin)['new_count'])")
TOTAL_COUNT=$(cat data/processed/update_stats.json | python -c "import sys,json; print(json.load(sys.stdin)['total_count'])")

if [ $((NEW_COUNT * 100 / TOTAL_COUNT)) -gt 5 ]; then
    echo "New papers exceed 5%, re-clustering..."
    python pipeline/03_embed.py --incremental
    python pipeline/04_cluster.py
    # ⚠️ 重新聚类后 cluster ID 会重新分配，需执行 ID 对齐
    python pipeline/04b_align_cluster_ids.py       # 与旧 cluster 做 cosine 相似度匹配，保持 ID 连续性
    python pipeline/05_name_clusters.py --only-new # 只对新 cluster 命名，旧 cluster 保留原名
fi

echo "Update complete."
```

**⚠️ Cluster ID 漂移问题**：
HDBSCAN 每次重新聚类会重新分配 cluster ID，导致历史数据中的 `cluster_id=3` 和新数据中的 `cluster_id=3` 指向不同方向。
`04b_align_cluster_ids.py` 通过计算新旧 cluster 质心的 cosine 相似度做匹配，保证同一研究方向在历史数据中 ID 不变。

---

## 安装依赖

### Python 环境

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

**requirements.txt**：
```
pandas==2.1.0
numpy==1.24.0
requests==2.31.0
tqdm==4.66.0
sentence-transformers==2.6.0  # 包含 SPECTER2
umap-learn==0.5.6
hdbscan==0.8.33
anthropic==0.25.0
fastapi==0.110.0
uvicorn==0.29.0
aiofiles==23.2.1
scikit-learn==1.4.0
```

### 前端环境

```bash
cd frontend
npm install
# 主要依赖
# echarts: ^5.4.3
# react: ^18.2.0
# tailwindcss: ^3.4.0
# axios: ^1.6.0
```

---

## 运行顺序（完整流程）

```bash
# 1. 设置 API Keys
export ANTHROPIC_API_KEY="your_key_here"
export SEMANTIC_SCHOLAR_API_KEY="your_key_here"  # 可选，不设置也可运行

# 2. 执行 Pipeline（按顺序）
python pipeline/01_fetch_data.py       # ~30 分钟（含 Semantic Scholar 请求）
python pipeline/02_filter_llm.py       # ~1 分钟
python pipeline/03_embed.py            # ~20 分钟（CPU）/ ~5 分钟（GPU）
python pipeline/04_cluster.py          # ~5 分钟
python pipeline/05_name_clusters.py    # ~3 分钟（API 调用）
python pipeline/06_compute_metrics.py  # ~2 分钟
python pipeline/07_export_api_data.py  # ~1 分钟

# 3. 启动后端
cd backend
uvicorn main:app --reload --port 8000

# 4. 启动前端
cd frontend
npm run dev
# 访问 http://localhost:5173
```

---

## 关键注意事项

1. **SPECTER2 首次下载**约 440MB 模型权重，需要网络连接
2. **Semantic Scholar API** 使用批量接口，25,000 篇约需 50 次请求（~2 分钟）；API Key 通过环境变量 `SEMANTIC_SCHOLAR_API_KEY` 注入，**不要硬编码到代码或文档中**
3. **聚类结果具有随机性**，`random_state=42` 保证可复现，建议先用 `min_cluster_size=50` 运行，根据实际 cluster 数量调整
4. **LLM 命名后需人工检查**：运行 `05_name_clusters.py` 后，打开 `data/processed/cluster_names.json`，将 `is_nlp_related=false` 的 cluster 的 `enabled` 字段设为 `false`
5. **ECharts ThemeRiver** 在 React 中需要手动 `useEffect` + `dispose`，注意内存泄漏
6. **papers.json 数据量**：不建议整体加载到前端，改为后端按 `cluster_id`/`year` 分片，前端按需请求
7. **Cluster ID 稳定性**：增量更新触发重新聚类时，必须运行 `04b_align_cluster_ids.py` 对齐新旧 ID，否则历史时间序列数据会错乱

---

## 预期成果

- 数据规模：约 15,000-25,000 篇论文（ACL 2018-2024，过滤后）
- 研究方向数量：约 50-70 个有意义的 cluster
- 主要方向示例（预期）：
  - Instruction Tuning & RLHF
  - Chain-of-Thought Reasoning
  - Machine Translation（经典方向，低 trend）
  - Named Entity Recognition（成熟方向）
  - Dialogue Systems
  - Parameter-Efficient Fine-Tuning（LoRA等）
  - Retrieval-Augmented Generation
  - Code Generation
  - Multilingual NLP
  - Commonsense Reasoning

---

*计划书版本：v1.0 | 预计总开发时间：10-15 天*
