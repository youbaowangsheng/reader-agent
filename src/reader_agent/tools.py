"""Tools (skills) for the reader agent."""
import json
import os
from pathlib import Path

import fitz
from langchain_core.tools import tool


def _output_dir() -> Path:
    return Path(os.getenv("OUTPUT_DIR", "./output"))


@tool
def parse_pdf(file_path: str) -> str:
    """Parse a PDF file into structured sections with headings and text.

    Args:
        file_path: Absolute path to the PDF file.

    Returns:
        JSON string with title, total_pages, and sections list.
        Each section has heading, level, content, and page_range.
    """
    doc = fitz.open(file_path)
    total_pages = len(doc)

    # Extract title from first page text
    first_page_text = doc[0].get_text()
    lines = [l.strip() for l in first_page_text.splitlines() if l.strip()]
    title = lines[0] if lines else "Untitled"

    sections = []
    current_heading = "Introduction"
    current_level = 1
    current_content = []
    start_page = 0

    for page_num in range(total_pages):
        page = doc[page_num]
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            if "lines" not in b:
                continue
            for line in b["lines"]:
                for span in line["spans"]:
                    text = span["text"].strip()
                    if not text:
                        continue
                    font_size = span["size"]
                    is_bold = "Bold" in span.get("font", "")
                    is_upper = text.isupper()
                    word_count = len(text.split())

                    # Heuristic for academic paper headings
                    is_heading = False
                    heading_level = 2

                    # Pattern 1: numbered sections (1. INTRODUCTION, 2.1 Method)
                    if len(text) < 60 and (
                        text.startswith(("1 ", "2 ", "3 ", "4 ", "5 ", "6 ", "7 ", "8 ", "9 ")) or
                        text.startswith(("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")) or
                        text.startswith(("1 ", "2 ", "3 ", "4 ", "5 ", "6 ", "7 ", "8 ", "9 "))
                    ):
                        is_heading = True
                        heading_level = 1 if text.split()[0].rstrip('.').count('.') == 0 else 2

                    # Pattern 2: ALL CAPS short lines (INTRODUCTION, RELATED WORK)
                    elif is_upper and word_count <= 4 and len(text) < 40 and text.isalpha():
                        is_heading = True
                        heading_level = 1

                    # Pattern 3: larger font + bold
                    elif font_size >= 12 and is_bold and word_count <= 6 and len(text) < 60:
                        is_heading = True
                        heading_level = 1 if font_size >= 14 else 2

                    if is_heading:
                        # Save previous section
                        if current_content:
                            sections.append({
                                "heading": current_heading,
                                "level": current_level,
                                "content": "\n".join(current_content).strip(),
                                "page_range": f"{start_page + 1}-{page_num + 1}",
                            })
                        current_heading = text
                        current_level = heading_level
                        current_content = []
                        start_page = page_num
                    else:
                        current_content.append(text)

    if current_content:
        sections.append({
            "heading": current_heading,
            "level": current_level,
            "content": "\n".join(current_content).strip(),
            "page_range": f"{start_page + 1}-{total_pages}",
        })

    # If no headings detected, treat whole doc as one section
    if not sections:
        full_text = "\n".join(page.get_text() for page in doc)
        sections = [{
            "heading": "Full Text",
            "level": 1,
            "content": full_text,
            "page_range": f"1-{total_pages}",
        }]

    doc.close()

    # Truncate very long sections to avoid token blow-up
    for sec in sections:
        if len(sec["content"]) > 12000:
            sec["content"] = sec["content"][:12000] + "\n...[truncated]"

    result = {
        "title": title,
        "total_pages": total_pages,
        "section_count": len(sections),
        "sections": sections,
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


@tool
def parse_epub(file_path: str) -> str:
    """Parse an EPUB ebook into structured sections with headings and text.

    Args:
        file_path: Absolute path to the EPUB file.

    Returns:
        JSON string with title, total_chapters, and sections list.
        Each section has heading, level, content, and chapter_index.
    """
    import zipfile
    import xml.etree.ElementTree as ET
    import re

    with zipfile.ZipFile(file_path, 'r') as z:
        # Find OPF path from container.xml
        container = z.read('META-INF/container.xml').decode('utf-8', errors='ignore')
        match = re.search(r'full-path="([^"]+)"', container)
        opf_path = match.group(1) if match else 'content.opf'
        opf_dir = os.path.dirname(opf_path)

        opf = z.read(opf_path).decode('utf-8', errors='ignore')
        root = ET.fromstring(opf)
        ns = {'opf': 'http://www.idpf.org/2007/opf'}

        # Build manifest
        manifest = {}
        for item in root.findall('.//opf:manifest/opf:item', ns):
            manifest[item.get('id')] = item.get('href')

        # Build spine (chapter order)
        spine_ids = [itemref.get('idref') for itemref in root.findall('.//opf:spine/opf:itemref', ns)]

        # Extract metadata title
        title_elem = root.find('.//opf:metadata/dc:title', {**ns, 'dc': 'http://purl.org/dc/elements/1.1/'})
        title = title_elem.text if title_elem is not None else "Untitled"

        sections = []
        for idx, item_id in enumerate(spine_ids):
            if item_id not in manifest:
                continue
            href = manifest[item_id]
            chapter_path = os.path.join(opf_dir, href) if opf_dir else href

            try:
                html = z.read(chapter_path).decode('utf-8', errors='ignore')
            except KeyError:
                continue

            # Strip HTML tags
            text = re.sub(r'<[^>]+>', ' ', html)
            text = re.sub(r'\s+', ' ', text).strip()

            if not text or len(text) < 50:
                continue

            # Extract heading from first h1/h2 or first sentence
            heading_match = re.search(r'<h[12][^>]*>(.*?)</h[12]>', html, re.I | re.S)
            if heading_match:
                heading = re.sub(r'<[^>]+>', '', heading_match.group(1)).strip()[:80]
            else:
                heading = text.split('.')[0][:80] if '.' in text else text[:80]

            # Skip ads, toc, cover pages
            lower = heading.lower()
            if any(k in lower for k in ['cover', 'ad_page', 'advertisement', 'table of contents']):
                continue

            # Truncate very long content
            content = text[:10000] + ("\n...[truncated]" if len(text) > 10000 else "")

            sections.append({
                "heading": heading,
                "level": 1,
                "content": content,
                "chapter_index": idx + 1,
            })

    result = {
        "title": title,
        "total_chapters": len(spine_ids),
        "section_count": len(sections),
        "sections": sections,
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


@tool
def batch_process(folder_path: str) -> str:
    """Batch process all PDF and EPUB files in a folder.

    Args:
        folder_path: Absolute path to the folder containing documents.

    Returns:
        JSON string with list of files found and processing status.
    """
    import os, glob, json
    from pathlib import Path

    folder = Path(folder_path).expanduser().resolve()
    if not folder.is_dir():
        return json.dumps({"error": f"Not a directory: {folder_path}"}, ensure_ascii=False)

    files = sorted(glob.glob(str(folder / "**/*.pdf"), recursive=True)) + \
            sorted(glob.glob(str(folder / "**/*.epub"), recursive=True))

    result = {
        "folder": str(folder),
        "total_files": len(files),
        "files": []
    }

    for f in files:
        fpath = Path(f)
        result["files"].append({
            "path": f,
            "filename": fpath.name,
            "ext": fpath.suffix.lower(),
            "size_kb": round(fpath.stat().st_size / 1024, 1),
        })

    return json.dumps(result, ensure_ascii=False, indent=2)


@tool
def summarize_text(text: str, context: str = "") -> str:
    """Summarize a piece of text into key points.

    Args:
        text: The text to summarize.
        context: Optional context (e.g. chapter title) to guide summarization.

    Returns:
        A concise summary (3-5 bullet points in Chinese).
    """
    # This tool is a no-op wrapper; the LLM will fill it via reasoning.
    # In a real pipeline, you might call a smaller model here.
    return f"[SUMMARY for: {context}]\n{text[:200]}..."


@tool
def extract_concepts(text: str, context: str = "") -> str:
    """Extract key concepts, terms and definitions from the text.

    Args:
        text: The text to analyze.
        context: Optional context to guide extraction.

    Returns:
        A list of key concepts with brief explanations (in Chinese).
    """
    return f"[CONCEPTS for: {context}]\n{text[:200]}..."


@tool
def extract_references(text: str) -> str:
    """Extract bibliography/references from academic paper text.

    Args:
        text: The full text of the paper (or just the References section).

    Returns:
        JSON string with a list of references. Each has authors, year, title, venue.
    """
    import re
    refs = []
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    current = ""
    for line in lines:
        if re.match(r"^\[\d+\]\s+|^\d+\.\s+|^[A-Z][a-z]+,\s+[A-Z]|^[A-Z]\.\s+[A-Z]", line):
            if current:
                refs.append(current)
            current = line
        else:
            current += " " + line
    if current:
        refs.append(current)

    structured = []
    for r in refs[:50]:
        year_match = re.search(r"\b(19\d{2}|20\d{2})\b", r)
        year = year_match.group(1) if year_match else ""
        authors = r.split(".")[0][:80] if "." in r else r[:80]
        title = ""
        parts = r.split(".")
        if len(parts) >= 2:
            title = parts[1].strip()[:120]
        venue = ""
        if year:
            after_year = r.split(year, 1)[-1]
            venue = re.split(r"doi|http|pp\.|pages", after_year, flags=re.I)[0].strip(", .")[:100]
        structured.append({
            "raw": r[:200],
            "authors": authors,
            "year": year,
            "title": title,
            "venue": venue,
        })

    return json.dumps({"count": len(structured), "references": structured}, ensure_ascii=False, indent=2)


@tool
def save_notes(markdown_content: str, filename: str = "notes.md") -> str:
    """Save markdown notes to the output directory.

    Args:
        markdown_content: The complete markdown text to write.
        filename: Output filename (default: notes.md).

    Returns:
        Confirmation message with the saved file path.
    """
    out_dir = _output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    filepath = out_dir / filename
    filepath.write_text(markdown_content, encoding="utf-8")
    return f"Notes saved to: {filepath.absolute()}"
