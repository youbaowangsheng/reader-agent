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
        data=json.dumps({'model': MODEL, 'messages': messages, 'temperature': 0.3}).encode(),
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {key}'},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.loads(r.read())
    return d['choices'][0]['message']['content']

def rate(title, body):
    prompt = f"""你是英语阅读教练。给下面这篇英文文章评定难度等级，并做规范化处理。

标题：{title}
正文（前 1600 词）：
{body[:1600]}

只返回 JSON（不要任何其他文字），格式：
{{"level":"L2","title_clean":"规范化的标题","fit":"精读","topic":"科技"}}

难度标准（面向高中学生）：
L1 初中拔高：短句、日常话题、少量生词（300-500词）
L2 会考基础：常见高中词汇、少量复合句
L3 高考过渡：出现长难句、科技/文化话题
L4 高考标准：抽象话题、词汇密度高
L5 高考压轴：长难句、复杂论证、时事评论

fit 取值：精读（600-1200词、有观点/论证、值得逐段带读）或 泛读（150-300词、或信息类短文、抓大意即可）。
如果文章太长(>2000词)或不适合学生，fit 填"不适合"。"""
    try:
        out = call([{'role': 'user', 'content': prompt}])
        # 提取 JSON
        s = out.find('{')
        e = out.rfind('}')
        if s >= 0 and e > s:
            return json.loads(out[s:e + 1])
        return None
    except Exception as ex:
        return {'error': str(ex)}

arts = json.load(open('/tmp/wired_articles.json'))
rated = []
for i, a in enumerate(arts):
    r = rate(a['title'], a['body'])
    if r and 'error' not in r:
        rated.append({**a, **r})
        print(f"[{i+1}/{len(arts)}] {r.get('level','?')} {r.get('fit','?')} | {a['title'][:40]}")
    else:
        print(f"[{i+1}/{len(arts)}] 失败: {r}")
    time.sleep(0.5)

json.dump(rated, open('/tmp/rated_articles.json', 'w'), ensure_ascii=False, indent=2)
print(f'\n完成，评级 {len(rated)}/{len(arts)} 篇，写 /tmp/rated_articles.json')
