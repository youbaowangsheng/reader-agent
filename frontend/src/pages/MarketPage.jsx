import React, { useState } from 'react';

function MarketPage({ active }) {
  const [searchQuery, setSearchQuery] = useState('');

  const recommendations = [
    { tag: '效率优化', title: 'PagedAttention v2', subtitle: '刚出炉 · 12人正在读' },
    { tag: '理论分析', title: '稀疏注意力边界', subtitle: '你可能会质疑它的实验' },
    { tag: '多模态', title: 'CLIP 跨语言变体', subtitle: '隔壁实验室上周发的' }
  ];

  const hotPapers = [
    { title: 'Retrospective Attention', year: '2024', annotators: 23 },
    { title: 'LoRA 微调极限', year: '2024', annotators: 17 },
    { title: 'Transformer 数学本质', year: '2023', annotators: 9 }
  ];

  if (!active) return null;

  return (
    <div id="page-market" className="page">
      <div className="market-hero">
        <div style={{ flex: 1 }}>
          <h3>找论文</h3>
          <p>支持 DOI / PDF / 链接</p>
        </div>
        <input
          className="big-input"
          placeholder="例如：10.48550/arXiv.2401.12345 或拖拽文件…"
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
        />
      </div>

      <div className="section-header">
        <h4>AI 推荐橱窗</h4>
        <span>基于你的「大模型推理」项目</span>
      </div>

      <div className="rec-list">
        {recommendations.map((rec, i) => (
          <div key={i} className="rec-item">
            <div className="tag">{rec.tag}</div>
            <div className="title">{rec.title}</div>
            <div className="subtitle">{rec.subtitle}</div>
            <button className="btn-add">+ 收入书架</button>
          </div>
        ))}
      </div>

      <h4 style={{ margin: '20px 0 12px', color: 'var(--text)' }}>共享预印本池 · 热读榜</h4>

      <div className="hot-list">
        {hotPapers.map((paper, i) => (
          <div key={i} className="hot-item">
            <div className="info">
              <strong>{paper.title}</strong>
              <span style={{ color: 'var(--text-4)', fontSize: '13px' }}>· {paper.year}</span>
              <span style={{ color: 'var(--text-4)', fontSize: '13px' }}>· {paper.annotators}人批注</span>
            </div>
            <button className="btn-add-light">+ 加入书架</button>
          </div>
        ))}
      </div>
    </div>
  );
}

export default MarketPage;
