"""Streamlit UI for Reader Agent — Reading-first design."""
import os
import re
import sys
import time
from pathlib import Path

import markdown as md_lib
import streamlit as st
from streamlit.components.v1 import html

sys.path.insert(0, str(Path(__file__).parent / "src"))

from reader_agent.graph import build_agent
from reader_agent.tools import parse_pdf, parse_epub

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "./output"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

st.set_page_config(page_title="Reader Agent", layout="wide", initial_sidebar_state="collapsed")

# ── Session State ───────────────────────────────
def init_state():
    defaults = {
        "selected_file": None,
        "current_view": "welcome",
        "font_size": 18,
        "line_height": 1.8,
        "content_width": 800,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# ── Helpers ───────────────────────────────
def find_note_file(source_path: Path):
    stem = source_path.stem
    for m in sorted(OUTPUT_DIR.glob("*_阅读笔记.md")):
        if stem in m.name:
            return m
    return None


def parse_toc(markdown_text: str):
    """Extract headings from markdown for TOC."""
    toc = []
    for line in markdown_text.splitlines():
        m = re.match(r"^(#{1,3})\s+(.+)$", line)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            anchor = re.sub(r"[^\w\u4e00-\u9fff-]", "", title.replace(" ", "-"))[:40]
            toc.append({"level": level, "title": title, "anchor": anchor})
    return toc


def markdown_to_html(markdown_text: str, font_size: int = 18, line_height: float = 1.8) -> str:
    """Convert markdown to styled HTML with anchor IDs."""
    # Add anchor IDs to headings before converting
    def heading_anchor(match):
        hashes = match.group(1)
        title = match.group(2).strip()
        anchor = re.sub(r"[^\w\u4e00-\u9fff-]", "", title.replace(" ", "-"))[:40]
        return f'{hashes} <span id="{anchor}">{title}</span>'

    anchored = re.sub(r"^(#{1,3})\s+(.+)$", heading_anchor, markdown_text, flags=re.M)

    # Convert to HTML
    html_body = md_lib.markdown(anchored, extensions=["tables", "fenced_code"])

    # Wrap in custom CSS
    css = f"""
    <style>
        .reader-content {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
            font-size: {font_size}px;
            line-height: {line_height};
            color: #e0e0e0;
            max-width: {st.session_state.content_width}px;
            margin: 0 auto;
            padding: 20px 40px;
        }}
        .reader-content h1, .reader-content h2, .reader-content h3 {{
            color: #fff;
            font-weight: 600;
            margin-top: 2em;
            margin-bottom: 0.8em;
            scroll-margin-top: 80px;
        }}
        .reader-content h1 {{ font-size: {font_size * 1.6}px; border-bottom: 2px solid #333; padding-bottom: 0.3em; }}
        .reader-content h2 {{ font-size: {font_size * 1.3}px; border-bottom: 1px solid #333; padding-bottom: 0.2em; }}
        .reader-content h3 {{ font-size: {font_size * 1.1}px; }}
        .reader-content p {{ margin-bottom: 1.2em; text-align: justify; }}
        .reader-content blockquote {{
            border-left: 4px solid #4CAF50;
            margin: 1.5em 0;
            padding: 0.5em 1em;
            background: #1a1d24;
            color: #b0b0b0;
        }}
        .reader-content table {{
            border-collapse: collapse;
            width: 100%;
            margin: 1.5em 0;
            font-size: {font_size * 0.9}px;
        }}
        .reader-content th, .reader-content td {{
            border: 1px solid #333;
            padding: 8px 12px;
            text-align: left;
        }}
        .reader-content th {{
            background: #1a1d24;
            font-weight: 600;
        }}
        .reader-content tr:nth-child(even) {{ background: #15171d; }}
        .reader-content code {{
            background: #2a2d35;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: "SF Mono", Monaco, monospace;
            font-size: {font_size * 0.85}px;
        }}
        .reader-content pre {{
            background: #1a1d24;
            padding: 16px;
            border-radius: 8px;
            overflow-x: auto;
            margin: 1.5em 0;
        }}
        .reader-content pre code {{
            background: transparent;
            padding: 0;
        }}
        .reader-content ul, .reader-content ol {{
            margin-bottom: 1.2em;
            padding-left: 1.5em;
        }}
        .reader-content li {{ margin-bottom: 0.5em; }}
        .reader-content hr {{
            border: none;
            border-top: 1px solid #333;
            margin: 2em 0;
        }}
        .reader-content a {{
            color: #4CAF50;
            text-decoration: none;
        }}
        .reader-content a:hover {{
            text-decoration: underline;
        }}
        /* Scrollbar */
        ::-webkit-scrollbar {{ width: 8px; }}
        ::-webkit-scrollbar-track {{ background: #0e1117; }}
        ::-webkit-scrollbar-thumb {{ background: #333; border-radius: 4px; }}
        ::-webkit-scrollbar-thumb:hover {{ background: #555; }}
    </style>
    <div class="reader-content">
        {html_body}
    </div>
    """
    return css


def render_reader(content: str):
    """Render note content as a reader view."""
    st.markdown("---")

    # Toolbar
    cols = st.columns([1, 1, 1, 4])
    with cols[0]:
        st.session_state.font_size = st.slider("🔍 字号", 12, 28, st.session_state.font_size, key="fs")
    with cols[1]:
        st.session_state.line_height = st.slider("⏫ 行距", 1.2, 2.5, st.session_state.line_height, 0.1, key="lh")
    with cols[2]:
        st.session_state.content_width = st.slider("↔️ 宽度", 600, 1200, st.session_state.content_width, 50, key="cw")

    # TOC + Content
    toc = parse_toc(content)
    if toc:
        # Build TOC HTML
        toc_html = '<div style="background:#1a1d24;padding:16px;border-radius:8px;margin-bottom:20px;">'
        toc_html += '<h4 style="margin:0 0 12px 0;color:#4CAF50;">📑 目录</h4>'
        for item in toc:
            indent = (item["level"] - 1) * 20
            toc_html += f'<div style="margin-left:{indent}px;margin-bottom:6px;">'
            toc_html += f'<a href="#{item["anchor"]}" style="color:#b0b0b0;text-decoration:none;font-size:14px;">{item["title"]}</a>'
            toc_html += '</div>'
        toc_html += '</div>'
        html(toc_html, height=min(200 + len(toc) * 25, 400), scrolling=True)

    # Main content
    html_content = markdown_to_html(
        content,
        font_size=st.session_state.font_size,
        line_height=st.session_state.line_height,
    )
    html(html_content, height=800, scrolling=True)


# ── Sidebar ──────────────────────────────────────────
with st.sidebar:
    st.title("📚 Reader Agent")

    uploaded = st.file_uploader("上传 PDF / EPUB", type=["pdf", "epub"], accept_multiple_files=True)
    if uploaded:
        for f in uploaded:
            dest = OUTPUT_DIR / f.name
            if not dest.exists():
                dest.write_bytes(f.read())
                st.success(f"已上传: {f.name}")

    st.divider()
    st.subheader("📂 文件")

    pdf_epubs = sorted(OUTPUT_DIR.glob("*.pdf")) + sorted(OUTPUT_DIR.glob("*.epub"))
    md_files = sorted(OUTPUT_DIR.glob("*_阅读笔记.md"))
    processed_names = {m.name.replace("_阅读笔记.md", "") for m in md_files}

    for p in pdf_epubs:
        name = p.stem
        done = name in processed_names or any(name in m.name for m in md_files)
        icon = "✅" if done else "⬜"
        if st.button(f"{icon} {p.name}", key=f"sb_{p.name}"):
            st.session_state.selected_file = str(p)
            st.session_state.current_view = "file"
            st.rerun()

    st.divider()
    # Quick access to existing notes
    if md_files:
        st.subheader("📖 已读笔记")
        for m in md_files:
            display = m.name.replace("_阅读笔记.md", "")
            if st.button(f"📖 {display[:30]}", key=f"note_{m.name}"):
                st.session_state.selected_file = str(m)
                st.session_state.current_view = "reader"
                st.rerun()


# ── Main Content ──────────────────────────────────────────

view = st.session_state.current_view
selected_path = st.session_state.selected_file

# ====== Welcome Screen ======
if view == "welcome" or not selected_path:
    st.header("👋 Reader Agent")
    st.markdown("""
    **AI-powered reading assistant** — 上传 PDF/EPUB，自动生成结构化阅读笔记，直接在浏览器中舒适阅读。

    ### 快速开始
    1. 左侧上传 PDF 或 EPUB 文件
    2. 点击文件名
    3. 点击 "🚀 开始阅读并生成笔记"
    4. 等待完成，自动进入阅读模式
    """)

    if md_files:
        st.divider()
        st.subheader("📑 最近的笔记")
        cols = st.columns(min(len(md_files), 3))
        for i, m in enumerate(sorted(md_files, key=lambda x: x.stat().st_mtime, reverse=True)[:6]):
            with cols[i % 3]:
                display = m.name.replace("_阅读笔记.md", "")
                if st.button(f"📖 {display[:25]}", key=f"recent_{i}"):
                    st.session_state.selected_file = str(m)
                    st.session_state.current_view = "reader"
                    st.rerun()
    st.stop()


# ====== Reader View (direct note) ======
if view == "reader" and selected_path and Path(selected_path).suffix == ".md":
    note_path = Path(selected_path)
    st.header(f"📖 {note_path.name.replace('_阅读笔记.md', '')}")
    with open(note_path, encoding="utf-8") as f:
        render_reader(f.read())
    st.stop()


# ====== File View (source document) ======
file_path = Path(selected_path)
st.header(f"📄 {file_path.name}")

note_file = find_note_file(file_path)

# --- Already done -> go to reader ---
if note_file:
    st.success("✅ 笔记已生成 — 正在进入阅读模式...")
    st.session_state.selected_file = str(note_file)
    st.session_state.current_view = "reader"
    time.sleep(0.5)
    st.rerun()
    st.stop()

# --- Processing ---
if view == "processing":
    st.button("🚀 正在处理中...", type="primary", disabled=True)
    bar = st.progress(0)
    status = st.empty()

    try:
        status.info("📄 解析文档结构...")
        bar.progress(15)
        if file_path.suffix.lower() == ".pdf":
            parse_pdf.func(str(file_path))
        else:
            parse_epub.func(str(file_path))

        status.info("🧠 初始化 Agent...")
        bar.progress(35)
        agent = build_agent()

        status.info("✍️ Agent 正在分析并生成笔记（这可能需要几分钟）...")
        bar.progress(60)
        agent.invoke({
            "messages": [{"role": "user", "content": f"请阅读并生成笔记：{file_path}"}]
        })

        status.info("💾 保存笔记...")
        bar.progress(90)
        time.sleep(0.3)

        note_file = find_note_file(file_path)
        if note_file:
            bar.progress(100)
            status.success("✅ 完成！正在进入阅读模式...")
            st.session_state.selected_file = str(note_file)
            st.session_state.current_view = "reader"
            time.sleep(0.5)
            st.rerun()
        else:
            status.warning("⚠️ 未找到笔记，请刷新页面。")
    except Exception as e:
        status.error(f"❌ 失败: {e}")
        st.exception(e)
    st.stop()


# --- Ready to start ---
st.warning("⏳ 尚未生成笔记")
if st.button("🚀 开始阅读并生成笔记", type="primary"):
    st.session_state.current_view = "processing"
    st.rerun()
