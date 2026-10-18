"""杂志拆分服务：上传杂志 PDF → 拆分 → 评级 → 入库（精读/泛读语料）。"""
import fitz
import re
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.service.llm import LLMService

# Wired 格式 dateline：Jan 02, 2025 10:30 AM（带时间）
dateline_full = re.compile(
    r'^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?,?\s+20\d\d\s+\d{1,2}:\d{2}\s+(AM|PM)'
)
# Economist 格式日期：Jul 23rd 2026（无时间）
dateline_date = re.compile(
    r'^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?,?\s+20\d\d$'
)
# Economist 文章边界：栏目 | 标签（如 "Leaders | In praise of hypocrisy"）
SECTION_TAG_RE = re.compile(r'^([A-Z][\w\s&\-]+?)\s*\|\s*(.+)$')
NAV = {'Next', 'Section menu', 'Main menu', 'Previous', 'Menu', 'Skip to', 'Share', 'Play/Pause Button'}
NOISE_PREFIX = ('ILLUSTRAT', 'PHOTOGRAPH', 'Play/Pause', 'CULTURE', '|')
SMALL_WORDS = {'the', 'a', 'an', 'of', 'and', 'or', 'to', 'in', 'on', 'for', 'with', 'by', 'at', 'as', 'is', 'are', 'was', 'were', 'be', 'into', 'up', 'out'}


def is_titlecase_line(s):
    words = [w for w in re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", s)]
    if not words:
        return False
    meaningful = [w for w in words if w.lower() not in SMALL_WORDS]
    if not meaningful:
        return False
    cap = [w for w in words if w[0].isupper() and w.lower() not in SMALL_WORDS]
    return len(cap) / len(meaningful) >= 0.6


def clean_line(s):
    if s in NAV or s.startswith('|') or s.startswith(NOISE_PREFIX):
        return None
    if re.fullmatch(r'\d+', s):
        return None
    return s


def split_pdf(path) -> List[Dict[str, Any]]:
    """拆分杂志 PDF（自动识别 Economist「栏目|标签」或 Wired dateline 格式）。"""
    doc = fitz.open(path)
    lines = []
    for i in range(len(doc)):
        for ln in doc[i].get_text().split('\n'):
            s = ln.strip()
            if s:
                lines.append(s)
    doc.close()

    section_bounds = [i for i, s in enumerate(lines) if SECTION_TAG_RE.match(s)]
    if section_bounds:
        return _split_by_section(lines, section_bounds)

    dateline_bounds = [i for i, s in enumerate(lines) if dateline_full.match(s)]
    if dateline_bounds:
        return _split_by_dateline(lines, dateline_bounds)

    return []


def _split_by_section(lines, bounds) -> List[Dict[str, Any]]:
    """Economist 格式：按「栏目 | 标签」行切分。"""
    articles = []
    for bi, idx in enumerate(bounds):
        end = bounds[bi + 1] if bi + 1 < len(bounds) else len(lines)
        m = SECTION_TAG_RE.match(lines[idx])
        section = m.group(1).strip()
        tail = lines[idx + 1:end]

        # 找日期行，标题在日期前
        date_idx = None
        for k, s in enumerate(tail):
            if dateline_date.match(s):
                date_idx = k
                break

        if date_idx is None:
            # 无日期行：前 3 行作标题，其余为正文
            head = tail[:3]
            body_tail = tail[3:]
        else:
            head = tail[:date_idx]
            body_tail = tail[date_idx + 1:]
        # Economist 标题是句子式（首词大写），不是 Title Case，直接用日期前的行作标题，
        # 评级时 LLM 的 clean_title 会规范化（去掉副标题）。
        title = ' '.join(head).strip()[:160]

        body_parts = []
        for s in body_tail:
            c = clean_line(s)
            if c:
                body_parts.append(c)
        body = ' '.join(body_parts)

        wc = len(body.split())
        if 250 <= wc <= 6000 and title:
            articles.append({
                'title': title,
                'author': '',
                'section': section,
                'date': '',
                'word_count': wc,
                'body': body,
            })
    return articles


def _split_by_dateline(lines, bounds) -> List[Dict[str, Any]]:
    """Wired 格式：按 dateline（带时间）切分。"""
    articles = []
    for bi, idx in enumerate(bounds):
        before = []
        j = idx - 1
        while j >= 0 and len(before) < 3:
            s = lines[j]
            if s in NAV or s.startswith('|') or dateline_full.match(s):
                break
            before.insert(0, s)
            j -= 1
        author = before[0] if before else ''
        section = before[1] if len(before) >= 2 else ''

        end = bounds[bi + 1] if bi + 1 < len(bounds) else len(lines)
        tail = lines[idx + 1:end]

        title_lines = []
        body_start = 0
        for k, s in enumerate(tail):
            if s in NAV or s.startswith(NOISE_PREFIX):
                continue
            if is_titlecase_line(s) and len(title_lines) < 6 and k < 12:
                title_lines.append(s)
                body_start = k + 1
            else:
                break
        title = ' '.join(title_lines).strip()

        body_parts = []
        for s in tail[body_start:]:
            c = clean_line(s)
            if c:
                body_parts.append(c)
        body = ' '.join(body_parts)

        wc = len(body.split())
        if 250 <= wc <= 6000 and title:
            articles.append({
                'title': title,
                'author': author,
                'section': section,
                'date': lines[idx],
                'word_count': wc,
                'body': body,
            })
    return articles


def _split_long_body(body: str, max_wc: int = 1500, min_wc: int = 250) -> List[str]:
    """长文按句子边界切到 min-max 词的段（供精读入库，避免逐段导读超 token 上限）。"""
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z"“\'])', body.strip())
    chunks = []
    cur = []
    cur_wc = 0
    for s in sentences:
        wc = len(s.split())
        if cur and cur_wc + wc > max_wc:
            chunks.append(' '.join(cur))
            cur = []
            cur_wc = 0
        cur.append(s)
        cur_wc += wc
    if cur:
        chunks.append(' '.join(cur))
    merged = []
    for ch in chunks:
        if merged and len(ch.split()) < min_wc:
            merged[-1] += ' ' + ch
        else:
            merged.append(ch)
    return merged


class MagazineService:
    """杂志/期刊拆分阅读：上传 → 拆分 → 评级 → 入库。"""

    def __init__(self):
        self.data_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data")
        self.magazines_path = os.path.join(self.data_dir, "magazines.json")
        self.storage_dir = os.path.join(
            os.path.dirname(__file__), "..", "..", "storage", "magazines"
        )
        os.makedirs(self.storage_dir, exist_ok=True)

    def _load(self) -> List[Dict[str, Any]]:
        try:
            with open(self.magazines_path, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _save(self) -> None:
        with open(self.magazines_path, "w", encoding="utf-8") as f:
            json.dump(self._load(), f, ensure_ascii=False, indent=2)

    def save_upload(self, filename: str, content: bytes) -> Dict[str, Any]:
        """保存上传的 PDF 并拆分，返回杂志记录（含拆出的文章列表）。"""
        mid = uuid.uuid4().hex[:12]
        pdf_path = os.path.join(self.storage_dir, f"{mid}.pdf")
        with open(pdf_path, "wb") as f:
            f.write(content)

        try:
            articles = split_pdf(pdf_path)
        except Exception:
            articles = []

        mag = {
            "id": mid,
            "filename": filename,
            "status": "split" if articles else "empty",
            "article_count": len(articles),
            "articles": articles,
            "imported": {"intensive": 0, "extensive": 0, "skipped": 0},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        mags = self._load()
        mags.insert(0, mag)
        with open(self.magazines_path, "w", encoding="utf-8") as f:
            json.dump(mags, f, ensure_ascii=False, indent=2)
        return mag

    def list_magazines(self) -> List[Dict[str, Any]]:
        return [
            {"id": m["id"], "filename": m["filename"], "status": m["status"],
             "article_count": m["article_count"], "imported": m.get("imported", {}),
             "created_at": m.get("created_at", "")}
            for m in self._load()
        ]

    def get_magazine(self, mid: str) -> Optional[Dict[str, Any]]:
        for m in self._load():
            if m["id"] == mid:
                return m
        return None

    def _update(self, mag: Dict[str, Any]) -> None:
        mags = self._load()
        for i, m in enumerate(mags):
            if m["id"] == mag["id"]:
                mags[i] = mag
                break
        with open(self.magazines_path, "w", encoding="utf-8") as f:
            json.dump(mags, f, ensure_ascii=False, indent=2)

    async def import_articles(self, mid: str) -> Dict[str, Any]:
        """评级拆出的文章并入库到精读/泛读语料。"""
        mag = self.get_magazine(mid)
        if not mag:
            return {"error": "杂志不存在"}
        if mag["status"] == "importing":
            return {"error": "正在导入中"}
        if not mag.get("articles"):
            return {"error": "没有可导入的文章，先拆分"}

        mag["status"] = "importing"
        self._update(mag)

        llm = LLMService()
        imported = {"intensive": 0, "extensive": 0, "skipped": 0}
        for a in mag["articles"]:
            body = a.get("body", "")
            wc = len(body.split())
            # 长文切分成段，每段单独评级入库（避免精读导读超 token 截断）
            segments = _split_long_body(body) if wc > 1500 else [body]
            for si, seg_body in enumerate(segments):
                seg = {**a, "body": seg_body, "word_count": len(seg_body.split())}
                if len(segments) > 1:
                    seg["title"] = a["title"] + f" (Part {si + 1}/{len(segments)})"
                try:
                    r = await llm.rate_article(seg["title"], seg["body"])
                except Exception as e:
                    r = {"error": str(e)}
                if not r or "error" in r:
                    imported["skipped"] += 1
                    continue
                fit = r.get("fit", "")
                if fit == "精读":
                    self._append_intensive(seg, r)
                    imported["intensive"] += 1
                elif fit == "泛读":
                    self._append_extensive(seg, r)
                    imported["extensive"] += 1
                else:
                    imported["skipped"] += 1

        mag["status"] = "done"
        mag["imported"] = imported
        self._update(mag)
        return imported

    def _append_intensive(self, a: Dict[str, Any], r: Dict[str, Any]) -> None:
        path = os.path.join(self.data_dir, "articles_v1.json")
        data = json.load(open(path, encoding="utf-8"))
        title_clean = r.get("title_clean") or a["title"]
        # 防御：title_clean 含中文（LLM 误翻译）则回退原文标题
        if re.search(r'[\u4e00-\u9fff]', title_clean):
            title_clean = a["title"]
        data.append({
            "title": title_clean,
            "author": a.get("author", ""),
            "section": a.get("section", ""),
            "date": a.get("date", ""),
            "word_count": a.get("word_count", len(a["body"].split())),
            "body": a["body"],
            "source": "magazine",
            "level": r.get("level", "L4"),
            "title_clean": r.get("title_clean", ""),
            "fit": "精读",
            "topic": r.get("topic", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _append_extensive(self, a: Dict[str, Any], r: Dict[str, Any]) -> None:
        path = os.path.join(self.data_dir, "news_articles.json")
        data = json.load(open(path, encoding="utf-8"))
        title_clean = r.get("title_clean") or a["title"]
        if re.search(r'[\u4e00-\u9fff]', title_clean):
            title_clean = a["title"]
        data.append({
            "title": title_clean,
            "body": a["body"],
            "word_count": a.get("word_count", len(a["body"].split())),
            "source": "magazine",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
