import React from 'react';

// 按标题哈希生成稳定的色相，让每篇文章/期刊有自己固定的封面颜色
export function hashHue(s) {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return h % 360;
}

// 小色块缩略图：列表项左图，色块上显示一两个关键词
export function Thumb({ title = '', keyword = '', size = 'md' }) {
  const seed = keyword || title || 'a';
  const hue = hashHue(seed);
  const words = (title || '').split(/\s+/).filter(Boolean).slice(0, 2);
  const text = keyword || words.join(' ');
  return (
    <div
      className={`thumb thumb-${size}`}
      style={{ background: `linear-gradient(150deg, hsl(${hue} 55% 42%), hsl(${(hue + 40) % 360} 62% 26%))` }}
    >
      <span className="thumb-text">{text}</span>
    </div>
  );
}

// 统一的封面卡片：无真实封面时用渐变 + 标题生成「书封面」观感
function Cover({ title = '', type = '', subtitle = '' }) {
  const seed = title || type || 'cover';
  const hue = hashHue(seed);
  const grad = `linear-gradient(155deg, hsl(${hue} 58% 40%), hsl(${(hue + 48) % 360} 68% 22%))`;
  return (
    <div className="cover" style={{ background: grad }}>
      {type && <span className="cover-type">{type}</span>}
      <span className="cover-title">{title}</span>
      {subtitle && <span className="cover-sub">{subtitle}</span>}
    </div>
  );
}

export default Cover;
