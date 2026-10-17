"""把精读长文按句子边界切分成 800-1500 词的短文（匹配 AI 导读的输出上限）。

背景：Wired 原文 4000-6000 词，逐段导读输出会超过 deepseek-chat 的 8192 tokens
上限被截断。精读产品定位是 800-1200 词短文，故把长文切分。
"""
import json
import re

MIN_WC = 700
MAX_WC = 1500

SENT_RE = re.compile(r'(?<=[.!?])\s+(?=[A-Z"“\'])')


def split_body(body):
    sentences = SENT_RE.split(body.strip())
    chunks = []
    cur = []
    cur_wc = 0
    for s in sentences:
        wc = len(s.split())
        if cur and cur_wc + wc > MAX_WC:
            chunks.append(' '.join(cur))
            cur = []
            cur_wc = 0
        cur.append(s)
        cur_wc += wc
    if cur:
        chunks.append(' '.join(cur))

    # 合并太短的尾部 chunk（不足 MIN_WC）到前一个
    merged = []
    for ch in chunks:
        if merged and len(ch.split()) < MIN_WC:
            merged[-1] = merged[-1] + ' ' + ch
        else:
            merged.append(ch)
    return merged


def main():
    src = json.load(open('data/articles_v1.json', encoding='utf-8'))
    # 备份原文（长文版）
    json.dump(src, open('data/articles_v1_long.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)

    out = []
    for a in src:
        body = a.get('body', '')
        wc = len(body.split())
        if wc <= MAX_WC:
            # 直接保留（短文）
            a['word_count'] = wc
            out.append(a)
        else:
            # 切分长文
            parts = split_body(body)
            for i, p in enumerate(parts):
                pw = len(p.split())
                if pw < 200:  # 太碎，丢弃
                    continue
                suffix = f'（节选 {i+1}/{len(parts)}）' if len(parts) > 1 else ''
                out.append({
                    **{k: v for k, v in a.items() if k != 'body' and k != 'word_count'},
                    'title': a['title'] + suffix,
                    'body': p,
                    'word_count': pw,
                })

    print(f'切分后总篇数: {len(out)}（原 {len(src)}）')
    wcs = sorted(x['word_count'] for x in out)
    print(f'词数: min={wcs[0]} 中位={wcs[len(wcs)//2]} max={wcs[-1]}')
    buckets = {'<700': 0, '700-1500': 0, '>1500': 0}
    for w in wcs:
        if w < 700:
            buckets['<700'] += 1
        elif w <= 1500:
            buckets['700-1500'] += 1
        else:
            buckets['>1500'] += 1
    print('分布:', buckets)

    json.dump(out, open('data/articles_v1.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)
    print('已写 data/articles_v1.json')


if __name__ == '__main__':
    main()
