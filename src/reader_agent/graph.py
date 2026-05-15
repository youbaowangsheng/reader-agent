"""Single-agent ReAct graph with reading skills."""
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from reader_agent.tools import parse_pdf, parse_epub, save_notes, extract_references, batch_process

load_dotenv()

SYSTEM_PROMPT = """你是一个专业的学术阅读助手。你的任务是根据用户提供的PDF、EPUB文件或文件夹，生成一份结构化的深度阅读笔记。

工作流程：
1. 判断用户输入：
   - 若是单个文件（.pdf/.epub），调用 `parse_pdf` 或 `parse_epub` 解析
   - 若是文件夹，先调用 `batch_process` 扫描获取文件列表，然后逐个处理
2. 基于解析结果，在思考中完成分析：
   - 用一句话概括全书/全文核心论点
   - 逐章提炼3-5个要点（中文）
   - 提取10-15个关键术语/概念
   - 写出2-3条批判性思考或疑问
3. 在笔记中增加图谱：
   - 概念关系图：Mermaid流程图(graph LR)，至少3-5个节点
   - 引用图谱：对References章节调用`extract_references`，展示前10条重要引用
4. 调用 `save_notes` 保存笔记。若是批量处理，每个文件处理完后都保存笔记，最后生成一份 `index.md` 列出所有处理结果。

笔记格式要求：
```markdown
# 《标题》阅读笔记

> 作者/来源：xxx | 页数：xxx

## 一句话总结
...

## 章节要点
### 第1章 xxx
- ...

## 核心概念
| 术语 | 解释 |
|------|------|
| ... | ... |

## 概念关系图
```mermaid
graph LR
    A[核心概念A] --> B[核心概念B]
    B --> C[结果/影响]
    ...
```

## 引用图谱
| 作者 | 年份 | 题目 | 来源 |
|------|------|------|------|
| ... | ... | ... | ... |

## 批判性思考
1. ...

## 原文摘录
- "..." (p.x)
```

注意：
- 所有分析内容使用中文
- 如果章节内容被截断，基于已有内容分析即可
- 输出文件命名格式：{标题}_阅读笔记.md
"""


def build_agent():
    api_key = os.getenv("DEEPSEEK_API_KEY")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY not set")

    # DeepSeek is OpenAI-compatible
    llm = ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=0.3,
        max_tokens=8192,
    )

    tools = [parse_pdf, parse_epub, extract_references, save_notes, batch_process]
    return create_react_agent(model=llm, tools=tools, prompt=SYSTEM_PROMPT)
