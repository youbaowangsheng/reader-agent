import urllib.request, re, json, time, html as htmlmod

CHANNELS = ['world', 'china', 'business', 'tech', 'culture', 'sports']
UA = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}

NOISE = re.compile(r'(copyright|all rights reserved|share to|facebook|twitter|linkedin|weibo|weixin|chinadaily\.com\.cn|recommended|related|most popular)', re.I)
LINK_RE = re.compile(r'href="(//www\.chinadaily\.com\.cn/a/\d+/\d+/WS[^"]+?\.html)"[^>]*>(.*?)</a>', re.S)


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=20).read().decode('utf-8', errors='ignore')


def strip_tags(s):
    s = re.sub(r'<[^>]+>', ' ', s)
    return htmlmod.unescape(s)


def fetch_list(channel):
    url = f'https://www.chinadaily.com.cn/{channel}/'
    try:
        html = fetch(url)
    except Exception as e:
        print(f'  [{channel}] 列表页失败: {e}')
        return []
    items = []
    seen = set()
    for m in LINK_RE.finditer(html):
        link, raw_title = m.group(1), m.group(2)
        title = strip_tags(raw_title).strip()
        if title and link not in seen:
            seen.add(link)
            items.append((title, link))
    return items


def fetch_article(link):
    try:
        html = fetch('https:' + link)
    except Exception:
        return None

    # 标题
    m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
    if not m:
        return None
    title = strip_tags(m.group(1)).strip()
    if len(title) < 3:
        return None

    # 正文：优先 <div id="Content">，回退到全文
    body_html = ''
    m = re.search(r'<div id="Content"[^>]*>(.*?)</div>\s*(?:<div|</body|<footer)', html, re.S)
    if m:
        body_html = m.group(1)
    else:
        body_html = html

    body_parts = []
    for pm in re.finditer(r'<p[^>]*>(.*?)</p>', body_html, re.S):
        t = strip_tags(pm.group(1)).strip()
        if not t:
            continue
        if len(t) < 20:
            continue
        if NOISE.search(t):
            continue
        body_parts.append(t)

    body = ' '.join(body_parts)
    wc = len(body.split())
    if wc < 150 or wc > 800:
        return None
    return {'title': title, 'body': body, 'word_count': wc}


def main():
    articles = []
    seen_titles = set()
    for ch in CHANNELS:
        items = fetch_list(ch)
        print(f'[{ch}] 列表 {len(items)} 条')
        for title, link in items[:15]:
            a = fetch_article(link)
            if a and a['title'] not in seen_titles:
                seen_titles.add(a['title'])
                a['source'] = f'chinadaily_{ch}'
                a['link'] = link
                articles.append(a)
            time.sleep(0.3)
    print(f'\n共抓到 {len(articles)} 篇泛读短文')
    wcs = sorted(a['word_count'] for a in articles)
    if wcs:
        print(f'词数 min={wcs[0]} 中位={wcs[len(wcs)//2]} max={wcs[-1]}')
    out = 'data/news_articles.json'
    json.dump(articles, open(out, 'w'), ensure_ascii=False, indent=2)
    print(f'已写 {out}')


if __name__ == '__main__':
    main()
