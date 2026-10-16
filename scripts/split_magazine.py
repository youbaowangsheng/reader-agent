import fitz, re, json

dateline = re.compile(r'^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},\s+20\d\d\s+\d{1,2}:\d{2}\s+(AM|PM)')
NAV = {'Next', 'Section menu', 'Main menu', 'Previous', 'Menu', 'Skip to', 'Share', 'Play/Pause Button'}
NOISE_PREFIX = ('ILLUSTRAT', 'PHOTOGRAPH', 'Play/Pause', 'CULTURE', '|')

def is_titlecase_line(s):
    words = [w for w in re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", s)]
    if not words:
        return False
    small = {'the','a','an','of','and','or','to','in','on','for','with','by','at','as','is','are','was','were','be','into','up','out'}
    cap = [w for w in words if w[0].isupper() and w.lower() not in small]
    meaningful = [w for w in words if w.lower() not in small]
    if not meaningful:
        return False
    return len(cap) / len(meaningful) >= 0.6

def clean_line(s):
    if s in NAV or s.startswith('|') or s.startswith(NOISE_PREFIX):
        return None
    # 去页码、去纯数字
    if re.fullmatch(r'\d+', s):
        return None
    return s

def split_wired(path):
    doc = fitz.open(path)
    pages = [(i + 1, doc[i].get_text()) for i in range(len(doc))]
    doc.close()
    global_lines = []
    for pageno, text in pages:
        for ln in text.split('\n'):
            s = ln.strip()
            if s:
                global_lines.append((pageno, s))
    bounds = [i for i, (p, s) in enumerate(global_lines) if dateline.match(s)]

    articles = []
    for bi, idx in enumerate(bounds):
        # 作者(上上行) + 栏目(上一行)
        before = []
        j = idx - 1
        while j >= 0 and len(before) < 3:
            s = global_lines[j][1]
            if s in NAV or s.startswith('|') or dateline.match(s):
                break
            before.insert(0, s)
            j -= 1
        author = before[0] if before else ''
        section = before[1] if len(before) >= 2 else ''

        end = bounds[bi + 1] if bi + 1 < len(bounds) else len(global_lines)
        tail = global_lines[idx + 1:end]

        title_lines = []
        body_start = 0
        for k, (pno, s) in enumerate(tail):
            if s in NAV or s.startswith(NOISE_PREFIX):
                continue
            if is_titlecase_line(s) and len(title_lines) < 6 and k < 12:
                title_lines.append(s)
                body_start = k + 1
            else:
                break
        title = ' '.join(title_lines).strip()
        body_parts = []
        for (pno, s) in tail[body_start:]:
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
                'date': global_lines[idx][1],
                'word_count': wc,
                'body': body,
                'source': 'wired_2025.01.02',
            })
    return articles

if __name__ == '__main__':
    arts = split_wired('/tmp/magazines/wired.pdf')
    wcs = sorted(a['word_count'] for a in arts)
    print(f'有效 {len(arts)} 篇；词数 min={wcs[0]} 中位={wcs[len(wcs)//2]} max={wcs[-1]}')
    with open('/tmp/magazines/wired_articles.json', 'w') as f:
        json.dump(arts, f, ensure_ascii=False, indent=2)
    print('已写 /tmp/magazines/wired_articles.json')
    for a in arts[:6]:
        print(f"  [{a['word_count']}词] {a['title'][:50]} | {a['author'][:20]} / {a['section'][:20]}")
