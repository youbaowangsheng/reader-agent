import React from 'react';

function PDFViewer({ fileUrl, onTextSelect }) {
  if (!fileUrl) {
    return <div className="pdf-error">没有文件 URL</div>;
  }

  return (
    <div className="pdf-viewer">
      <div className="pdf-toolbar">
        <span>PDF 阅读器 - 使用浏览器内置查看器</span>
      </div>
      <div className="pdf-container">
        <iframe
          src={fileUrl}
          title="PDF Viewer"
          style={{
            width: '100%',
            height: '100%',
            border: 'none',
          }}
        />
      </div>
    </div>
  );
}

export default PDFViewer;