import re
import json
from typing import List, Tuple, Dict, Any
from pathlib import Path
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


def parse_pdf(file_path: str) -> Dict[str, Any]:
    """Parse PDF into structured sections with headings and text."""
    doc = pymupdf.open(file_path)
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

                    # Pattern 1: numbered sections
                    if len(text) < 60 and (
                        text.startswith(("1 ", "2 ", "3 ", "4 ", "5 ", "6 ", "7 ", "8 ", "9 "))
                        or text.startswith(("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9."))
                    ):
                        is_heading = True
                        heading_level = 1 if text.split()[0].rstrip(".").count(".") == 0 else 2

                    # Pattern 2: ALL CAPS short lines
                    elif is_upper and word_count <= 4 and len(text) < 40 and text.isalpha():
                        is_heading = True
                        heading_level = 1

                    # Pattern 3: larger font + bold
                    elif font_size >= 12 and is_bold and word_count <= 6 and len(text) < 60:
                        is_heading = True
                        heading_level = 1 if font_size >= 14 else 2

                    if is_heading:
                        if current_content:
                            sections.append(
                                {
                                    "heading": current_heading,
                                    "level": current_level,
                                    "content": "\n".join(current_content).strip(),
                                    "page_range": f"{start_page + 1}-{page_num + 1}",
                                }
                            )
                        current_heading = text
                        current_level = heading_level
                        current_content = []
                        start_page = page_num
                    else:
                        current_content.append(text)

    if current_content:
        sections.append(
            {
                "heading": current_heading,
                "level": current_level,
                "content": "\n".join(current_content).strip(),
                "page_range": f"{start_page + 1}-{total_pages}",
            }
        )

    if not sections:
        full_text = "\n".join(page.get_text() for page in doc)
        sections = [
            {
                "heading": "Full Text",
                "level": 1,
                "content": full_text,
                "page_range": f"1-{total_pages}",
            }
        ]

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

    with zipfile.ZipFile(file_path, "r") as z:
        container = z.read("META-INF/container.xml").decode("utf-8", errors="ignore")
        match = re.search(r'full-path="([^"]+)"', container)
        opf_path = match.group(1) if match else "content.opf"
        opf_dir = os.path.dirname(opf_path)

        opf = z.read(opf_path).decode("utf-8", errors="ignore")
        root = ET.fromstring(opf)
        ns = {"opf": "http://www.idpf.org/2007/opf"}

        # Build manifest
        manifest = {}
        for item in root.findall(".//opf:manifest/opf:item", ns):
            manifest[item.get("id")] = item.get("href")

        # Build spine (chapter order)
        spine_ids = [itemref.get("idref") for itemref in root.findall(".//opf:spine/opf:itemref", ns)]

        # Extract metadata title
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

            # Strip HTML tags
            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s+", " ", text).strip()

            if not text or len(text) < 50:
                continue

            # Extract heading from first h1/h2 or first sentence
            heading_match = re.search(r"<h[12][^>]*>(.*?)</h[12]>", html, re.I | re.S)
            if heading_match:
                heading = re.sub(r"<[^>]+>", "", heading_match.group(1)).strip()[:80]
            else:
                heading = text.split(".")[0][:80] if "." in text else text[:80]

            # Skip ads, toc, cover pages
            lower = heading.lower()
            if any(k in lower for k in ["cover", "ad_page", "advertisement", "table of contents"]):
                continue

            content = text[:10000] + ("\n...[truncated]" if len(text) > 10000 else "")

            sections.append(
                {
                    "heading": heading,
                    "level": 1,
                    "content": content,
                    "chapter_index": idx + 1,
                }
            )

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


import os