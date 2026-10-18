import React from 'react';

// 按标题哈希生成稳定的色相，让每篇文章/期刊有自己固定的封面颜色
function hashHue(s) {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return h % 360;
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
