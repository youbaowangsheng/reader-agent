"""Streamlit UI for Reader Agent."""
import os
import re
import sys
import time
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))

from reader_agent.service import (
    answer_question_with_rag,
    clear_recent_memory,
    find_note_file,
    generate_note_for_file,
    get_recent_memory,
    get_index_for_note,
    suggest_term_questions,
)

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "./output"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

st.set_page_config(page_title="Reader Agent", layout="wide", initial_sidebar_state="expanded")


def init_state():
    defaults = {
        "selected_file": None,
        "current_view": "welcome",
        "font_size": 17,
        "line_height": 1.7,
        "chat_by_note": {},
        "selected_section_idx": 0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def parse_headings(markdown_text: str) -> List[Tuple[int, str, int]]:
    items: List[Tuple[int, str, int]] = []
    for idx, line in enumerate(markdown_text.splitlines()):
        m = re.match(r"^(#{1,3})\s+(.+)$", line)
        if m:
            items.append((len(m.group(1)), m.group(2).strip(), idx))
    return items


def split_by_headings(markdown_text: str) -> List[Dict[str, str]]:
    lines = markdown_text.splitlines()
    headings = parse_headings(markdown_text)
    if not headings:
        return [{"title": "全文", "content": markdown_text}]

    sections: List[Dict[str, str]] = []
    for i, (_, title, start) in enumerate(headings):
        end = headings[i + 1][2] if i + 1 < len(headings) else len(lines)
        content = "\n".join(lines[start:end]).strip()
        sections.append({"title": title, "content": content})
    return sections


def ensure_chat_slot(note_key: str):
    if note_key not in st.session_state.chat_by_note:
        st.session_state.chat_by_note[note_key] = []


def render_answer(answer: Dict):
    st.markdown("### 回答")
    st.write(answer.get("answer", ""))
    facts = answer.get("facts", [])
    if facts:
        st.markdown("### 事实卡片")
        for i, f in enumerate(facts, start=1):
            claim = f.get("claim", "")
            conf = f.get("confidence", 0.0)
            evidence = f.get("evidence", "")
            st.markdown(f"{i}. **{claim}**")
            st.caption(f"置信度: {conf} | 证据: {evidence}")
    citations = answer.get("citations", [])
    if citations:
        st.markdown("### 引用依据")
        for i, c in enumerate(citations, start=1):
            heading = c.get("heading", "")
            page = c.get("page_range", "")
            chunk_id = c.get("chunk_id", "")
            quote = c.get("quote", "")
            st.markdown(f"{i}. `{chunk_id}` | {heading} | {page}")
            if quote:
                st.caption(quote)
    conflicts = answer.get("fact_conflicts", [])
    if conflicts:
        st.error("检测到与历史事实卡片可能冲突的结论，请重点复核引用。")
        for c in conflicts:
            st.caption(f"新结论: {c.get('new_claim', '')}")
            st.caption(f"历史结论: {c.get('old_claim', '')}")


def add_chat_turn(note_key: str, role: str, content: str, answer: Dict | None = None):
    ensure_chat_slot(note_key)
    row = {"role": role, "content": content}
    if answer is not None:
        row["answer"] = answer
    st.session_state.chat_by_note[note_key].append(row)


def ask_and_render(note_key: str, question: str, index_data: Dict, status_slot):
    chat_history = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.chat_by_note.get(note_key, [])
        if "content" in m and "role" in m
    ][-10:]

    with status_slot:
        with st.spinner("检索中并生成回答..."):
            result = answer_question_with_rag(question=question, index_data=index_data, chat_history=chat_history, top_k=5)
    add_chat_turn(note_key, "user", question)
    add_chat_turn(note_key, "assistant", result.get("answer", ""), answer=result)
    render_answer(result)


def render_reader(note_path: Path, note_text: str):
    st.markdown(
        f"""
<style>
div[data-testid="stMarkdownContainer"] p {{
  font-size: {st.session_state.font_size}px;
  line-height: {st.session_state.line_height};
}}
</style>
""",
        unsafe_allow_html=True,
    )

    sections = split_by_headings(note_text)
    headings = [s["title"] for s in sections]
    st.session_state.selected_section_idx = min(st.session_state.selected_section_idx, len(headings) - 1)

    top_cols = st.columns([1, 1, 3])
    with top_cols[0]:
        st.session_state.font_size = st.slider("字号", 12, 28, st.session_state.font_size, key="reader_font")
    with top_cols[1]:
        st.session_state.line_height = st.slider("行距", 1.2, 2.4, st.session_state.line_height, 0.1, key="reader_lh")

    body_cols = st.columns([2, 1])

    with body_cols[0]:
        idx = st.selectbox("章节导航", range(len(headings)), index=st.session_state.selected_section_idx, format_func=lambda i: headings[i])
        st.session_state.selected_section_idx = idx
        st.markdown("---")
        st.markdown(sections[idx]["content"])

    with body_cols[1]:
        st.subheader("论文问答")
        index_data = get_index_for_note(note_path)
        note_key = str(note_path.resolve())
        note_widget_key = hashlib.md5(note_key.encode("utf-8")).hexdigest()[:12]
        ensure_chat_slot(note_key)

        if not index_data:
            st.warning("该笔记未找到索引，无法进行引用式问答。请重新处理对应源文件。")
            return

        status_slot = st.empty()
        recent_memory = get_recent_memory(index_data, limit=4)
        st.markdown("#### 会话事实记忆")
        if recent_memory:
            for i, m in enumerate(recent_memory, start=1):
                st.markdown(f"{i}. **{m.get('claim', '')}**")
                st.caption(f"置信度: {m.get('confidence', 0.0)} | 证据: {m.get('evidence', '')}")
                citations = m.get("citations", [])
                if citations:
                    c = citations[0]
                    st.caption(f"引用: {c.get('chunk_id', '')} | {c.get('heading', '')} | {c.get('page_range', '')}")
            if st.button("清空记忆", key=f"clear_mem_{note_widget_key}"):
                clear_recent_memory(index_data)
                st.rerun()
        else:
            st.caption("暂无记忆")

        question = st.text_area("提问", placeholder="例如：这篇论文的方法和基线相比改进点是什么？", key=f"q_{note_widget_key}")
        if st.button("发送问题", key=f"ask_{note_widget_key}") and question.strip():
            ask_and_render(note_key, question.strip(), index_data, status_slot)

        st.markdown("#### 选中段落提问")
        selected_para = st.text_area(
            "粘贴你选中的段落",
            placeholder="把你正在读的段落粘贴到这里，然后点击提问",
            key=f"sel_{note_widget_key}",
            height=120,
        )
        if st.button("基于段落提问", key=f"ask_sel_{note_widget_key}") and selected_para.strip():
            ask_and_render(note_key, f"请解释这段内容并联系全文：\n{selected_para.strip()}", index_data, status_slot)

        st.markdown("#### 术语追问")
        term_prompts = suggest_term_questions(note_text)
        if term_prompts:
            selected_prompt = st.selectbox("选择术语问题", term_prompts, key=f"term_{note_widget_key}")
            if st.button("提问术语", key=f"ask_term_{note_widget_key}"):
                ask_and_render(note_key, selected_prompt, index_data, status_slot)

        if st.session_state.chat_by_note.get(note_key):
            st.markdown("#### 最近对话")
            for msg in st.session_state.chat_by_note[note_key][-6:]:
                role = "你" if msg["role"] == "user" else "AI"
                st.markdown(f"**{role}**: {msg['content']}")
                if msg["role"] == "assistant" and msg.get("answer", {}).get("citations"):
                    c = msg["answer"]["citations"][0]
                    st.caption(f"引用: {c.get('chunk_id', '')} | {c.get('heading', '')} | {c.get('page_range', '')}")


init_state()

with st.sidebar:
    st.title("Reader Agent")
    uploaded = st.file_uploader("上传 PDF / EPUB", type=["pdf", "epub"], accept_multiple_files=True)
    if uploaded:
        for f in uploaded:
            dest = OUTPUT_DIR / f.name
            if not dest.exists():
                dest.write_bytes(f.read())
                st.success(f"已上传: {f.name}")

    st.divider()
    st.subheader("文件")
    source_files = sorted(OUTPUT_DIR.glob("*.pdf")) + sorted(OUTPUT_DIR.glob("*.epub"))
    note_files = sorted(OUTPUT_DIR.glob("*_阅读笔记.md"))

    for p in source_files:
        done = find_note_file(p) is not None
        icon = "✅" if done else "⬜"
        if st.button(f"{icon} {p.name}", key=f"src_{p.name}"):
            st.session_state.selected_file = str(p)
            st.session_state.current_view = "file"
            st.rerun()

    st.divider()
    if note_files:
        st.subheader("笔记")
        for m in note_files:
            if st.button(f"📖 {m.name.replace('_阅读笔记.md', '')[:28]}", key=f"note_{m.name}"):
                st.session_state.selected_file = str(m)
                st.session_state.current_view = "reader"
                st.rerun()


view = st.session_state.current_view
selected_path = st.session_state.selected_file

if view == "welcome" or not selected_path:
    st.header("Reader Agent")
    st.markdown(
        """
上传 PDF/EPUB -> 生成阅读笔记 -> 在右侧对话面板进行“可引用问答”。

第一版能力：
- RAG 检索（chunk + embedding + vector store）
- 回答必须绑定引用 chunk/page/heading
- 选中段落提问
- 术语追问
"""
    )
    st.stop()


if view == "reader" and selected_path and Path(selected_path).suffix == ".md":
    note_path = Path(selected_path)
    st.header(f"📖 {note_path.name.replace('_阅读笔记.md', '')}")
    render_reader(note_path, note_path.read_text(encoding="utf-8"))
    st.stop()


file_path = Path(selected_path)
st.header(f"📄 {file_path.name}")
note_file = find_note_file(file_path)

if note_file:
    st.success("笔记已存在，进入阅读模式。")
    st.session_state.selected_file = str(note_file)
    st.session_state.current_view = "reader"
    time.sleep(0.2)
    st.rerun()
    st.stop()

if view == "processing":
    bar = st.progress(0)
    status = st.empty()
    try:
        status.info("解析文档并构建索引...")
        bar.progress(35)
        result = generate_note_for_file(file_path)
        bar.progress(100)
        status.success("完成，进入阅读模式。")
        st.session_state.selected_file = str(result.note_path)
        st.session_state.current_view = "reader"
        time.sleep(0.3)
        st.rerun()
    except Exception as e:
        status.error(f"处理失败: {e}")
        st.exception(e)
    st.stop()

st.warning("尚未生成笔记")
if st.button("开始处理", type="primary"):
    st.session_state.current_view = "processing"
    st.rerun()
