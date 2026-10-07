#!/usr/bin/env python3
"""Mock FIPAI service on port 8000 for testing."""
import json
import random
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

PORT = 8000

PAPER_ABSTRACT = """This paper presents a novel approach to machine learning optimization using adaptive gradient descent methods.
We propose a new algorithm called Adaptive Momentum (Adam) that combines the benefits of RMSProp and momentum-based optimization.
Our method achieves state-of-the-art results on multiple benchmark datasets including ImageNet and COCO."""

PAPER_CONTENT = {
    "title": "Adam: A Method for Stochastic Optimization",
    "authors": ["Diederik P. Kingma", "Jimmy Ba"],
    "abstract": PAPER_ABSTRACT,
    "sections": [
        {"heading": "1. Introduction", "content": "Optimization of neural networks is a fundamental challenge..."},
        {"heading": "2. Algorithm", "content": "We propose Adam, which maintains per-parameter learning rates..."},
        {"heading": "3. Related Work", "content": "Previous methods include SGD with momentum, RMSProp..."},
        {"heading": "4. Experiments", "content": "We evaluate on MNIST, CIFAR-10, and ImageNet..."},
    ]
}

def generate_answer(question: str, chunks: list) -> dict:
    """Generate a mock answer with citations."""
    q_lower = question.lower()

    if "about" in q_lower or "summary" in q_lower or "是什么" in q_lower:
        answer = f"""这篇论文是关于一种名为 **Adam (Adaptive Moment Estimation)** 的随机优化方法。

主要贡献：
1. 提出结合动量法和RMSProp优点的自适应学习率优化算法
2. 通过计算梯度的一阶和二阶矩估计来自适应调整学习率
3. 在多个基准数据集上达到最优性能

核心方法：Adam通过维护梯度的一阶矩（均值）m和二阶矩（方差）v的指数移动均值来自适应调整学习率，同时使用偏差校正来抵消初始化偏差。"""
        citations = chunks[:2] if len(chunks) >= 2 else chunks
    elif "method" in q_lower or "方法" in q_lower or "how" in q_lower:
        answer = """论文提出的Adam方法主要步骤：

**算法原理：**
1. 计算梯度一阶矩估计：m_t = β₁·m_{t-1} + (1-β₁)·g_t
2. 计算梯度二阶矩估计：v_t = β₂·v_{t-1} + (1-β₂)·g_t²
3. 偏差校正：m̂_t = m_t / (1-β₁^t), v̂_t = v_t / (1-β₂^t)
4. 更新参数：θ_{t+1} = θ_t - α·m̂_t / (√v̂_t + ε)

其中β₁=0.9, β₂=0.999, ε=10⁻⁸"""
        citations = [chunks[1]] if len(chunks) > 1 else chunks[:1]
    elif "experiment" in q_lower or "result" in q_lower or "实验" in q_lower or "效果" in q_lower:
        answer = """论文实验结果显示：

**MNIST实验：**
- Adam收敛速度最快，显著优于SGD和RMSProp
- 最终准确率达到99.2%

**CIFAR-10实验：**
- 使用CNN架构，Adam达到91.5%准确率
- 比RMSProp快约30%达到相同性能

**ImageNet实验：**
- 在大规模图像分类任务上表现优异
- top-5准确率达到89.2%"""
        citations = [chunks[3]] if len(chunks) > 3 else chunks[:1]
    else:
        answer = f"""根据论文内容，关于您的问题：

这篇论文主要研究深度学习优化算法，提出了Adam方法。论文表明Adam通过自适应调整学习率，能在各种深度学习任务中获得优异性能。

关键发现：
- 自适应学习率比固定学习率收敛更快
- 动量项有助于加速收敛并避免局部最优
- 偏差校正对早期迭代尤为重要"""
        citations = chunks[:1]

    return {
        "answer": answer,
        "citations": [
            {
                "chunk_id": c.get("chunk_id", f"chunk-{i}"),
                "heading": c.get("heading", "Unknown"),
                "page_range": c.get("page_range", "1"),
                "quote": c.get("text", c.get("content", ""))[:150] + "..."
            }
            for i, c in enumerate(citations)
        ] if citations else [],
        "facts": [
            {"claim": f"论文在实验中使用了{len(chunks)}个chunks的相关内容", "source": "experiment"},
            {"claim": "Adam算法使用β₁=0.9, β₂=0.999的超参数", "source": "algorithm"},
        ]
    }


def generate_note() -> str:
    return """## 一句话总结

Adam是一种结合动量法和自适应学习率的深度学习优化算法，通过一阶和二阶矩估计实现高效收敛。

## 核心概念

| 术语 | 定义 |
|------|------|
| Adam | Adaptive Moment Estimation，结合动量和自适应学习率的优化器 |
| 学习率 | 控制参数更新步长大小的超参数 |
| 动量 | 累积历史梯度加速收敛的技术 |
| 梯度 | 损失函数对参数的偏导数 |
| 收敛 | 优化过程趋于稳定的过程 |

## 批判性问题

1. 论文声称Adam在所有任务上都优于SGD，这一结论是否过于绝对？
2. 超参数β₁、β₂的选择是否具有理论依据，还是仅凭经验确定？
3. 在极深网络（如100+层）中，Adam是否仍能保持优异性能？
4. 论文未讨论计算开销，实际部署时效率如何？

## 整体评价

**创新性**: ★★★★☆ - 首次将动量与自适应学习率有效结合
**实验完整性**: ★★★★★ - 在多个数据集和任务上验证
**可复现性**: ★★★★☆ - 算法描述清晰，但超参数选择未充分说明
**写作质量**: ★★★★☆ - 结构清晰，但理论分析较少
"""


class MockFIPAIHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress logging

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else b'{}'

        try:
            data = json.loads(body.decode('utf-8'))
        except:
            data = {}

        input_data = data.get('input', {})
        task = input_data.get('task', '')

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()

        if task == 'answer_with_citations':
            result = generate_answer(
                question=input_data.get('question', ''),
                chunks=input_data.get('retrieved_chunks', [])
            )
            response = {
                "status": "success",
                "output": {
                    "report": result
                }
            }
        elif task == 'generate_reading_note':
            response = {
                "status": "success",
                "output": {
                    "report": {
                        "note_markdown": generate_note()
                    }
                }
            }
        elif task in ('generate_summary_10s', 'generate_summary_2m', 'generate_summary_10m'):
            response = {
                "status": "success",
                "output": {
                    "report": {
                        "final_markdown": f"这是论文的{task}摘要：本文提出Adam优化器，通过自适应学习率提升深度学习训练效率。"
                    }
                }
            }
        elif task == 'extract_fact_card':
            text = input_data.get('text', '')
            response = {
                "status": "success",
                "output": {
                    "report": {
                        "claim": f"从文本中提取的事实: {text[:50]}...",
                        "evidence": "实验数据支持",
                        "confidence": 0.85
                    }
                }
            }
        elif task == 'evaluate_paper':
            response = {
                "status": "success",
                "output": {
                    "report": {
                        "novelty": 4,
                        "rigor": 4,
                        "reproducibility": 4,
                        "pros": ["创新性强", "实验充分"],
                        "cons": ["理论分析不足"]
                    }
                }
            }
        else:
            response = {
                "status": "success",
                "output": {
                    "report": {"result": f"Mock response for task: {task}"}
                }
            }

        self.wfile.write(json.dumps(response).encode('utf-8'))


def run_server():
    server = HTTPServer(('0.0.0.0', PORT), MockFIPAIHandler)
    print(f"Mock FIPAI service running on http://0.0.0.0:{PORT}")
    server.serve_forever()


if __name__ == '__main__':
    run_server()
