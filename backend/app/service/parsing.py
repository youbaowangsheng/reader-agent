import re
import os
import json
from typing import List, Tuple, Dict, Any
from pathlib import Path
from collections import Counter
import pymupdf
import ebooklib
from ebooklib import epub
import zipfile
import xml.etree.ElementTree as ET

# Reuse chunking logic from original rag.py
def chunk_text(text: str, max_chars: int = 900, overlap_chars: int = 150) -> List[str]:
    """Split text into overlapping chunks."""
    text = re.sub(r"\s+", " ", (text or "")).strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks: List[str] = []
    start = 0
    step = max(1, max_chars - overlap_chars)
    while start < len(text):
        end = min(len(text), start + max_chars)
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start += step
    return [c for c in chunks if c]


def _extract_pages_lines(doc) -> List[List[Dict[str, Any]]]:
    """Extract per-page list of lines, each line = {text, size, bold, block}（block 用于段落合并）。"""
    pages = []
    for page in doc:
        lines = []
        block_idx = 0
        for b in page.get_text("dict")["blocks"]:
            if "lines" not in b:
                block_idx += 1
                continue
            for line in b["lines"]:
                spans = line["spans"]
                text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", "".join(s["text"] for s in spans)).strip()
                if not text:
                    continue
                max_size = max(s["size"] for s in spans)
                is_bold = any("Bold" in s.get("font", "") for s in spans)
                lines.append({"text": text, "size": max_size, "bold": is_bold, "block": block_idx, "y": line["bbox"][1]})
            block_idx += 1
        pages.append(lines)
    return pages


def _extract_images(doc, image_dir: str, basename: str) -> List[Dict[str, Any]]:
    """提取 PDF 图片（统一转 PNG），保存到 image_dir，返回 [{page, y, x, width, height, url}]。"""
    os.makedirs(image_dir, exist_ok=True)
    images = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        page_area = page.rect.width * page.rect.height
        seen = set()
        for img in page.get_images(full=True):
            xref = img[0]
            if xref in seen:
                continue
            seen.add(xref)
            rects = page.get_image_rects(xref)
            if not rects:
                continue
            x0, y0, x1, y1 = rects[0]
            area = (x1 - x0) * (y1 - y0)
            # 过滤封面背景图（面积 > 60%）和太小的装饰图标（< 1%）
            if area > page_area * 0.6 or area < page_area * 0.01:
                continue
            try:
                pix = pymupdf.Pixmap(doc, xref)
                if pix.n - pix.alpha >= 4:  # CMYK -> RGB
                    pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
                data = pix.tobytes("png")
            except Exception:
                continue
            if not data:
                continue
            fname = f"{basename}_p{page_num + 1}_{len(images)}.png"
            fpath = os.path.join(image_dir, fname)
            try:
                with open(fpath, "wb") as fh:
                    fh.write(data)
            except OSError:
                continue
            images.append({
                "page": page_num,
                "y": y0,
                "x": x0,
                "width": x1 - x0,
                "height": y1 - y0,
                "url": f"/storage/images/{fname}",
            })
    return images


def _is_toc_line(text: str) -> bool:
    """目录行特征：点线+页码，或 '数字 | 标题'，或 '标题 ... 页码'."""
    t = text.strip()
    if not t:
        return False
    # "Introduction ..... 5" 点线+页码
    if re.search(r"\.{3,}\s*\d+$", t):
        return True
    # "1 | Introduction" 或 "II  Executive Summary" 数字/罗马 + 标题
    if re.match(r"^[IVXLC\d]+[\s|·.]+[A-Z]", t):
        return True
    # "Executive Summary   VI" 标题 + 罗马页码
    if re.search(r"\s+[IVXLC]+$", t) and len(t.split()) >= 2:
        return True
    return False


def _is_table_row(text: str) -> bool:
    """检测表格数据行：token 数 >= 6 且数字 token 占比 >= 50%。"""
    tokens = text.split()
    if len(tokens) < 6:
        return False
    nums = sum(1 for t in tokens if re.match(r"^-?\d+\.?\d*%?$", t))
    return nums / len(tokens) >= 0.5


def _find_body_start(pages_lines: List[List[Dict]], total_pages: int) -> int:
    """定位正文起始页，跳过封面/版权/缩写/目录等 front matter."""
    # 1) 找目录页（front matter 前 1/3 内出现 "Contents"）
    toc_idx = -1
    for i, lines in enumerate(pages_lines):
        if i > total_pages // 3:
            break
        page_text = " ".join(l["text"] for l in lines).lower()
        if re.search(r"\b(table of contents|contents)\b", page_text):
            toc_idx = i
            break

    if toc_idx >= 0:
        # 从目录页往后，跳过目录页及目录续页（大量目录行）
        start = toc_idx
        while start < total_pages:
            lines = pages_lines[start]
            n_toc = sum(1 for l in lines if _is_toc_line(l["text"]))
            n_all = max(1, len(lines))
            # 目录页：目录行占比高，或页文本含 "contents"
            page_text = " ".join(l["text"] for l in lines).lower()
            if n_toc / n_all >= 0.3 or ("contents" in page_text and start == toc_idx):
                start += 1
                continue
            break
        return start

    # 2) 无目录：找第一个 abstract / introduction / numbered heading
    for i, lines in enumerate(pages_lines):
        for l in lines:
            lt = l["text"].strip().lower()
            if l["size"] >= 11 and lt in ("abstract", "introduction"):
                return i
            # numbered heading（要求字号足够大，排除正文/附录里的列表项如 "1. xxx"）
            if l["size"] >= 11 and re.match(r"^[1-9][.\s]", l["text"]):
                return i
    # 3) 默认跳过封面（第 0 页）
    return min(1, total_pages - 1)


def _build_header_footer_set(pages_lines: List[List[Dict]], total_pages: int) -> Tuple[set, set]:
    """跨页重复的短行 = 页眉页脚；并处理 '书名 | 页码' 形式."""
    cnt = Counter()
    prefix_cnt = Counter()
    for lines in pages_lines:
        for t in {l["text"] for l in lines if len(l["text"]) < 80}:
            cnt[t] += 1
            # "China's Economic Transition | II" -> 前缀 "China's Economic Transition"
            m = re.match(r"^(.*?)\s*[|\-–—]\s*[IVXLC\d]+\s*$", t)
            if m:
                prefix_cnt[m.group(1).strip()] += 1

    threshold = max(3, int(total_pages * 0.25))
    hf = {t for t, c in cnt.items() if c >= threshold}
    hf_prefixes = {p for p, c in prefix_cnt.items() if c >= threshold}
    return hf, hf_prefixes


# 常见全大写章节标题词白名单（用于区分真标题与表格里的模型缩写如 HGT/GAT）
_SECTION_CAPS = {
    "ABSTRACT", "INTRODUCTION", "CONCLUSION", "CONCLUSIONS",
    "METHODOLOGY", "METHOD", "METHODS", "MATERIALS AND METHODS",
    "RESULTS", "RESULT", "DISCUSSION", "RELATED WORK", "BACKGROUND",
    "REFERENCES", "REFERENCE", "SUMMARY", "OVERVIEW", "ACKNOWLEDGMENTS",
    "ACKNOWLEDGEMENTS", "APPENDIX", "FUTURE WORK", "LIMITATIONS",
    "EXPERIMENTS", "EXPERIMENTAL SETUP", "EVALUATION", "DATASET", "DATASETS",
    "PRELIMINARIES", "PROBLEM STATEMENT", "APPROACH", "CONTRIBUTIONS",
    "OUTLINE", "CONCLUDING REMARKS", "NOTATION", "DEFINITIONS",
}


def _is_heading(text: str, size: float, is_bold: bool, is_upper: bool, word_count: int) -> Tuple[bool, int]:
    """判断是否为 section heading，返回 (is_heading, level)。排除目录项/页码。"""
    t = text.strip()
    # 排除纯罗马数字（目录项 I / II / III）
    if re.match(r"^[IVXLC]+\.?$", t):
        return False, 0
    # 排除纯数字/小数（页码、表格数值如 8.42）
    if re.match(r"^[\d.,\s]+$", t):
        return False, 0
    # 排除上标编号+机构连写（如 4KAIST / 1University of Oxford）
    if re.match(r"^\d+[A-Za-z]", t):
        return False, 0
    # 排除目录行（点线页码 / 数字|标题 / 标题+罗马页码）
    if _is_toc_line(t):
        return False, 0

    # Pattern 1: numbered sections
    # "1 Introduction"（数字 + 空格 + 大写字母）
    if re.match(r"^[1-9]\s+[A-Z]", t):
        return True, 1
    # "1.1 Search phase"（数字.数字 + 大写，subsection）
    if re.match(r"^[1-9]\.[1-9]\s*[A-Z]", t):
        return True, 2
    # "1. Introduction"（数字. + 大写）
    if re.match(r"^[1-9]\.\s*[A-Z]", t):
        return True, 1

    # Pattern 2: ALL CAPS 章节标题词（白名单，避免把表格模型缩写 HGT/GAT 当标题）
    if is_upper and t.upper().rstrip(".") in _SECTION_CAPS:
        return True, 1

    # Pattern 3: larger font + bold
    if size >= 12 and is_bold and word_count <= 6 and len(t) < 60:
        level = 1 if size >= 14 else 2
        return True, level

    return False, 0


def parse_pdf(file_path: str) -> Dict[str, Any]:
    """Parse PDF into structured sections, skipping front matter and filtering headers/footers."""
    doc = pymupdf.open(file_path)
    total_pages = len(doc)

    pages_lines = _extract_pages_lines(doc)

    # 提取图片（统一转 PNG，保存到 storage/images/）
    basename = os.path.splitext(os.path.basename(file_path))[0]
    image_dir = os.path.join(os.path.dirname(os.path.abspath(file_path)), "images")
    images = _extract_images(doc, image_dir, basename)
    images_by_page: Dict[int, List[Dict]] = {}
    for img in sorted(images, key=lambda im: (im["page"], im["y"])):
        images_by_page.setdefault(img["page"], []).append(img)

    # 过滤页眉页脚
    hf_lines, hf_prefixes = _build_header_footer_set(pages_lines, total_pages)

    # 找正文起始页
    body_start = _find_body_start(pages_lines, total_pages)

    # 提取标题：优先 PDF 元数据；否则第一页最大字号行（合并，排除单字母 drop cap）
    title = ""
    meta_title = (doc.metadata or {}).get("title", "").strip()
    if meta_title and meta_title.lower() not in ("untitled", "microsoft word", "latex", ""):
        title = meta_title
    if not title and pages_lines and pages_lines[0]:
        first_page = pages_lines[0]
        max_size = max((l["size"] for l in first_page), default=0)
        big = [l["text"] for l in first_page if l["size"] >= max_size - 0.5 and len(l["text"]) > 1]
        if big:
            title = " ".join(big)
    if not title:
        first_lines = [l["text"] for l in (pages_lines[0] if pages_lines else []) if l["text"]]
        title = first_lines[0] if first_lines else "Untitled"

    # 从 body_start 解析 sections
    sections = []
    current_heading = "Introduction"
    current_level = 1
    current_paras: List[str] = []       # 段落列表（每段已合并物理断行）
    current_para_lines: List[str] = []  # 当前段落累积的行
    last_block = None
    table_buffer: List[str] = []
    start_page = body_start

    def flush_table():
        nonlocal table_buffer
        if table_buffer:
            current_paras.append("[TABLE]" + "\n".join(table_buffer))
            table_buffer = []

    def flush_para():
        nonlocal current_para_lines
        if current_para_lines:
            current_paras.append(" ".join(current_para_lines))
            current_para_lines = []

    def flush_heading(end_page):
        nonlocal current_paras, start_page, last_block
        flush_table()
        flush_para()
        if current_paras:
            sections.append({
                "heading": current_heading,
                "level": current_level,
                "content": "\n\n".join(current_paras).strip(),
                "page_range": f"{start_page + 1}-{end_page + 1}",
            })
        current_paras = []
        start_page = end_page
        last_block = None

    for page_num in range(body_start, total_pages):
        lines = pages_lines[page_num]
        page_images = images_by_page.get(page_num, [])
        img_ptr = 0
        idx = 0
        while idx < len(lines):
            l = lines[idx]
            text = l["text"]
            # 图片插入：图片在当前行上方时，先插入图片段落
            if img_ptr < len(page_images) and page_images[img_ptr]["y"] < l.get("y", 0):
                flush_para()
                current_paras.append("[IMAGE:" + page_images[img_ptr]["url"] + "]")
                img_ptr += 1
                continue
            # 过滤页眉页脚（完整行）
            if text in hf_lines:
                idx += 1
                continue
            # 过滤 "前缀 | 页码" 形式的页眉
            m = re.match(r"^(.*?)\s*[|\-–—]\s*[IVXLC\d]+\s*$", text)
            if m and m.group(1).strip() in hf_prefixes:
                idx += 1
                continue

            # 检测 "编号行 + 标题行" 分行的章节（arXiv：'1' 行 + 'Introduction' 行；附录 'A' + 标题）
            combined = None
            if re.match(r"^[A-Z0-9]{1,2}$", text) and l["size"] >= 11 and idx + 1 < len(lines):
                nxt = lines[idx + 1]
                nt = nxt["text"]
                if (nxt["size"] >= 11 and 2 <= len(nt) < 60
                        and nt[0].isupper() and not nt.isupper()
                        and not re.match(r"^[\d.,\s]+$", nt)
                        and not _is_toc_line(nt)):
                    combined = f"{text} {nt}"

            if combined:
                flush_heading(page_num)
                current_heading = combined
                current_level = 1
                idx += 2
                continue

            is_heading, level = _is_heading(text, l["size"], l["bold"], text.isupper(), len(text.split()))
            if is_heading:
                flush_heading(page_num)
                current_heading = text
                current_level = level
            else:
                if _is_table_row(text):
                    # 表格数据行：独立成段，保留行结构（前端等宽渲染）
                    flush_para()
                    table_buffer.append(text)
                    last_block = None
                elif (len(text) < 25 and re.search(r"[A-Za-z]", text)
                      and idx + 1 < len(lines) and _is_table_row(lines[idx + 1]["text"])):
                    # 模型名行（下一行是数值行）→ 归入表格
                    flush_para()
                    table_buffer.append(text)
                    last_block = None
                else:
                    if table_buffer:
                        flush_table()
                    # 段落合并：block 变化 = 段落边界，否则同一段落（去掉物理断行）
                    blk = l.get("block")
                    if last_block is not None and blk != last_block:
                        flush_para()
                    current_para_lines.append(text)
                    last_block = blk
            idx += 1

        # 页面剩余图片（在最后文本行之后）
        while img_ptr < len(page_images):
            flush_para()
            current_paras.append("[IMAGE:" + page_images[img_ptr]["url"] + "]")
            img_ptr += 1

    # flush 最后一节
    flush_table()
    flush_para()
    if current_paras:
        sections.append({
            "heading": current_heading,
            "level": current_level,
            "content": "\n\n".join(current_paras).strip(),
            "page_range": f"{start_page + 1}-{total_pages}",
        })

    if not sections:
        full_text = "\n".join(page.get_text() for page in doc)
        sections = [{"heading": "Full Text", "level": 1, "content": full_text, "page_range": f"1-{total_pages}"}]

    doc.close()

    # Truncate very long sections
    for sec in sections:
        if len(sec["content"]) > 12000:
            sec["content"] = sec["content"][:12000] + "\n...[truncated]"

    return {
        "title": title,
        "total_pages": total_pages,
        "section_count": len(sections),
        "sections": sections,
    }


def parse_epub(file_path: str) -> Dict[str, Any]:
    """Parse EPUB into structured sections with headings and text."""
    import re
    import os

    with zipfile.ZipFile(file_path, "r") as z:
        container = z.read("META-INF/container.xml").decode("utf-8", errors="ignore")
        match = re.search(r'full-path="([^"]+)"', container)
        opf_path = match.group(1) if match else "content.opf"
        opf_dir = os.path.dirname(opf_path)

        opf = z.read(opf_path).decode("utf-8", errors="ignore")
        root = ET.fromstring(opf)
        ns = {"opf": "http://www.idpf.org/2007/opf"}

        manifest = {}
        for item in root.findall(".//opf:manifest/opf:item", ns):
            manifest[item.get("id")] = item.get("href")

        spine_ids = [itemref.get("idref") for itemref in root.findall(".//opf:spine/opf:itemref", ns)]

        title_elem = root.find(".//opf:metadata/dc:title", {**ns, "dc": "http://purl.org/dc/elements/1.1/"})
        title = title_elem.text if title_elem is not None else "Untitled"

        sections = []
        for idx, item_id in enumerate(spine_ids):
            if item_id not in manifest:
                continue
            href = manifest[item_id]
            chapter_path = os.path.join(opf_dir, href) if opf_dir else href

            try:
                html = z.read(chapter_path).decode("utf-8", errors="ignore")
            except KeyError:
                continue

            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s+", " ", text).strip()

            if not text or len(text) < 50:
                continue

            heading_match = re.search(r"<h[12][^>]*>(.*?)</h[12]>", html, re.I | re.S)
            if heading_match:
                heading = re.sub(r"<[^>]+>", "", heading_match.group(1)).strip()[:80]
            else:
                heading = text.split(".")[0][:80] if "." in text else text[:80]

            lower = heading.lower()
            if any(k in lower for k in ["cover", "ad_page", "advertisement", "table of contents"]):
                continue

            content = text[:10000] + ("\n...[truncated]" if len(text) > 10000 else "")
            sections.append({"heading": heading, "level": 1, "content": content, "chapter_index": idx + 1})

    return {
        "title": title,
        "total_chapters": len(spine_ids),
        "section_count": len(sections),
        "sections": sections,
    }


def parse_document(file_path: str) -> Dict[str, Any]:
    """Parse document based on file extension."""
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return parse_pdf(file_path)
    elif suffix == ".epub":
        return parse_epub(file_path)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")
