# Reader Agent

Reader Agent 是“英文论文阅读业务层”。
它负责文档解析、阅读任务编排、笔记渲染；AI 推理能力通过可切换后端提供（直连模型或 FIPAI 中台）。

## 业务层 vs 中台层

- 业务层（Reader Agent）：
  - PDF/EPUB 解析
  - 阅读笔记结构定义
  - Streamlit 阅读交互
  - 笔记存储与管理
- 中台层（FIPAI）：
  - 模型路由、重试、降级
  - 统一鉴权与调用审计
  - 成本/Token 统计
  - Agent 实例化与工作流编排

## Features

- PDF & EPUB 结构化解析
- 学术阅读笔记自动生成（摘要/概念/引用/批判性思考）
- 本地 RAG：chunk + embedding + JSON vector store + citation metadata
- 阅读页对话面板（回答附带 chunk/page/heading 引用）
- 交互入口：自由提问 / 选中段落提问 / 术语追问
- 会话级事实记忆（同一篇文献多轮问答自动带入已确认结论）
- 结构化事实卡片（结论/证据/置信度，可在阅读页回顾）
- Streamlit 阅读模式（字号/行距可调 + 章节导航）
- 可切换 AI Provider：`direct` 或 `fipai`

## Tech Stack

| Layer | Tool |
|-------|------|
| Business Layer | Python + Streamlit |
| Parsing | PyMuPDF + 标准库 EPUB 解析 |
| AI Backend Adapter | Direct LLM / FIPAI Instance API |
| Dependency Management | Poetry |

## Quick Start

### 1. Setup

```bash
cd reader-agent
cp .env.example .env
```

### 2. Install

```bash
poetry install
```

### 3. Configure AI backend

`direct`（默认，直连 OpenAI-compatible API）:

```bash
AI_PROVIDER=direct
DEEPSEEK_API_KEY=...
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

`fipai`（通过 FIPAI 中台实例）:

```bash
AI_PROVIDER=fipai
FIPAI_BASE_URL=http://127.0.0.1:8000
FIPAI_INSTANCE_ID=<instance-uuid>
FIPAI_BEARER_TOKEN=<optional>
FIPAI_API_KEY=<optional>
```

如果你使用当前仓库里 FIPAI 的 `seed` 数据，Reader 实例默认是：
`FIPAI_INSTANCE_ID=bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb`

### 4. Run

```bash
streamlit run app.py
```

CLI（单文件）:

```bash
PYTHONPATH=src python -m reader_agent ~/Downloads/paper.pdf
```

## Architecture

```text
[User Input: PDF/EPUB]
        |
        v
[Reader Agent Business Service]
  |- parse_pdf / parse_epub
  |- build rag index (chunks + embeddings)
  |- build reading task
  |- qa with citations
  |- save note markdown
        |
        v
[AI Backend Adapter]
  |- DirectLLMBackend (legacy/direct)
  |- FIPAIBackend (platform)
        |
        v
[Output: *_阅读笔记.md]
[RAG Index: output/.rag/doc_xxx.json]
```

## FIPAI 对接约定（当前版本）

`generate_reading_note` 任务：
- 入参：`input.task=generate_reading_note` + `input.document`
- 返回：`output.note_markdown`（或兼容字段）

`answer_with_citations` 任务：
- 入参：`input.task=answer_with_citations` + `input.question` + `input.retrieved_chunks`
- 推荐返回：
```json
{
  "output": {
    "answer": "...",
    "citations": [
      {"chunk_id": "...", "quote": "...", "heading": "...", "page_range": "..."}
    ]
  }
}
```

## Environment Variables

```bash
AI_PROVIDER=direct

DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

FIPAI_BASE_URL=http://127.0.0.1:8000
FIPAI_INSTANCE_ID=
FIPAI_BEARER_TOKEN=
FIPAI_API_KEY=
FIPAI_TIMEOUT_SEC=120

RAG_MIN_CITATIONS=2
OUTPUT_DIR=./output
```

## Project Structure

```text
reader-agent/
├── app.py
├── src/reader_agent/
│   ├── __main__.py
│   ├── ai_backend.py    # AI backend adapter (direct/fipai)
│   ├── service.py       # business orchestration
│   ├── tools.py         # parser and note persistence
│   └── graph.py         # legacy react agent (optional)
├── pyproject.toml
└── output/
```
