import json, os, sys, time
import urllib.request

# 读 DeepSeek key
key = None
for p in ['/opt/speakingcoach/backend/.env', '/opt/readingcoach/backend/.env']:
    if os.path.exists(p):
        for line in open(p):
            if line.startswith('DEEPSEEK_API_KEY='):
                key = line.strip().split('=', 1)[1]
                break
    if key:
        break
if not key:
    print('未找到 DEEPSEEK_API_KEY'); sys.exit(1)

BASE = 'https://api.deepseek.com'
MODEL = 'deepseek-chat'

def call(messages):
    req = urllib.request.Request(
        BASE + '/chat/completions',
        data=json.dumps({'model': MODEL, 'messages': messages, 'temperature': 0}).encode(),
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {key}'},
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())['choices'][0]['message']['content']

def clean_body(title, body):
    prompt = f"""你是文本清洗助手。下面是一篇英文文章正文，从 PDF 提取，混入了图片/图表的说明文字。

请严格做以下**删除**，其余正文**一字不改**（不要改写、不要翻译、不要增删正文内容、不要重新分段）：

1. 删除图片来源/作者信息：如 "Photograph: Tom Cockram"、"Photo: Getty Images"、"Illustration: SI PARMEGGIANI"、"Photography: JLR"、"Credit: Reuters" 等（前缀 + 人名/机构名/含斜杠的作者）
2. 删除图片/图表标题说明（caption）：图片下方描述图片内容的孤立短句

只输出清洗后的正文文本本身，不要任何解释、不要 markdown 包裹、不要加标题。

标题：{title}

正文：
{body}"""
    try:
        return call([{'role': 'user', 'content': prompt}])
    except Exception as e:
        print(f'  失败: {e}')
        return body  # 失败返回原文

arts = json.load(open('articles_v1.json'))
for i, a in enumerate(arts):
    before = len(a['body'].split())
    a['body'] = clean_body(a['title'], a['body'])
    after = len(a['body'].split())
    print(f"[{i+1}/{len(arts)}] {a['title'][:40]} | 词数 {before} -> {after}")
    time.sleep(0.3)

json.dump(arts, open('articles_v1.json', 'w'), ensure_ascii=False, indent=2)
print('\n完成，已写回 articles_v1.json')
