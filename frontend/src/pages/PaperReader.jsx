import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import PDFViewer from '../components/PDFViewer';

function PaperReader() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [paper, setPaper] = useState(null);
  const [notes, setNotes] = useState(null);
  const [question, setQuestion] = useState('');
  const [selectedText, setSelectedText] = useState('');
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('pdf'); // 'pdf', 'notes', 'chat'
  const [sessionId] = useState(() => localStorage.getItem(`session_${id}`) || crypto.randomUUID());

  // Auth check - redirect to login if no token
  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) {
      navigate('/');
      return;
    }
    api.setToken(token);
  }, [navigate]);

  useEffect(() => {
    localStorage.setItem(`session_${id}`, sessionId);
  }, [sessionId, id]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [paperRes] = await Promise.all([
          api.getPaper(id).catch(() => ({ data: null })),
        ]);
        setPaper(paperRes.data);

        // Try to get notes
        if (paperRes.data?.status === 'ready') {
          try {
            const notesRes = await api.getNotes(id);
            setNotes(notesRes.data);
          } catch (e) {
            // If notes do not exist yet, trigger async generation once
            try {
              await api.generateNotes(id);
            } catch (genErr) {
              console.log('Trigger note generation failed:', genErr?.response?.data || genErr?.message);
            }
            console.log('No notes yet');
          }
        }
      } catch (err) {
        console.error('Failed to fetch paper:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [id]);

  useEffect(() => {
    if (!paper || paper.status !== 'ready' || notes) return undefined;
    const timer = setInterval(async () => {
      try {
        const notesRes = await api.getNotes(id);
        setNotes(notesRes.data);
      } catch (_) {
        // keep polling until generated
      }
    }, 5000);
    return () => clearInterval(timer);
  }, [paper, notes, id]);

  const handleAsk = async () => {
    if (!question.trim()) return;

    const userMsg = { role: 'user', content: question };
    setMessages(prev => [...prev, userMsg]);
    setQuestion('');

    try {
      const res = await api.askQuestion(id, question, sessionId);
      const assistantMsg = {
        role: 'assistant',
        content: res.data.answer,
        citations: res.data.citations,
        facts: res.data.facts,
      };
      setMessages(prev => [...prev, assistantMsg]);
    } catch (err) {
      const errorMsg = err.response?.data?.detail || err.message || '抱歉，回答失败。';
      setMessages(prev => [...prev, { role: 'assistant', content: `错误: ${errorMsg}` }]);
    }
  };

  const handleTextSelect = (text) => {
    setSelectedText(text);
    setQuestion(`请解释这段内容：\n${text}`);
    setActiveTab('chat');
  };

  if (loading) return <div className="loading">加载中...</div>;
  if (!paper) return <div className="error">论文未找到</div>;

  // Backend returns file_url like "/storage/{uuid_filename}" or "./storage/{uuid_filename}"
  // Normalize to "/storage/{uuid_filename}" for Vite proxy
  const fileUrl = paper.file_url
    ? paper.file_url.replace(/^\.\//, '/')  // "./storage" → "/storage"
    : '';

  return (
    <div className="reader-layout-full">
      <div className="reader-header">
        <h1>{paper.filename}</h1>
        <div className="reader-tabs">
          <button
            className={activeTab === 'pdf' ? 'active' : ''}
            onClick={() => setActiveTab('pdf')}
          >
            📄 PDF阅读
          </button>
          <button
            className={activeTab === 'notes' ? 'active' : ''}
            onClick={() => setActiveTab('notes')}
          >
            📝 笔记
          </button>
          <button
            className={activeTab === 'chat' ? 'active' : ''}
            onClick={() => setActiveTab('chat')}
          >
            💬 对话
          </button>
        </div>
      </div>

      <div className="reader-content-layout">
        {/* PDF Viewer Tab */}
        {activeTab === 'pdf' && (
          <div className="pdf-viewer-container">
            <PDFViewer fileUrl={fileUrl} onTextSelect={handleTextSelect} />
          </div>
        )}

        {/* Notes Tab */}
        {activeTab === 'notes' && (
          <div className="notes-container">
            {notes ? (
              <>
                {notes.summary && (
                  <div className="note-section">
                    <h3>📌 摘要</h3>
                    <p>{notes.summary}</p>
                  </div>
                )}
                {notes.key_concepts?.length > 0 && (
                  <div className="note-section">
                    <h3>📚 核心概念</h3>
                    <table className="concepts-table">
                      <thead>
                        <tr>
                          <th>术语</th>
                          <th>定义</th>
                        </tr>
                      </thead>
                      <tbody>
                        {notes.key_concepts.map((c, i) => (
                          <tr key={i}>
                            <td>{c.term}</td>
                            <td>{c.definition}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                {notes.critical_questions?.length > 0 && (
                  <div className="note-section">
                    <h3>❓ 批判性问题</h3>
                    <ul>
                      {notes.critical_questions.map((q, i) => (
                        <li key={i}>{q}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            ) : (
              <div className="no-notes">
                <p>暂无笔记</p>
                <p>点击"开始解析"生成笔记后可见</p>
              </div>
            )}
          </div>
        )}

        {/* Chat Tab */}
        {activeTab === 'chat' && (
          <div className="chat-container">
            <div className="chat-messages">
              {messages.map((msg, i) => (
                <div key={i} className={`message ${msg.role}`}>
                  <div className="message-content">{msg.content}</div>
                  {msg.citations?.length > 0 && (
                    <div className="message-citations">
                      <small>引用: {msg.citations.map(c => `${c.heading} (${c.page_range})`).join(', ')}</small>
                    </div>
                  )}
                </div>
              ))}
            </div>
            {selectedText && (
              <div className="selected-text-hint">
                <small>已选择文字，可基于此提问</small>
              </div>
            )}
            <div className="chat-input">
              <textarea
                value={question}
                onChange={e => setQuestion(e.target.value)}
                placeholder="输入问题..."
                onKeyDown={e => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleAsk();
                  }
                }}
              />
              <button onClick={handleAsk}>发送</button>
            </div>
          </div>
        )}

        {/* Side Panel - always visible for large screens */}
        <div className="reader-sidebar">
          <h3>💬 对话</h3>
          <div className="chat-messages-sidebar">
            {messages.map((msg, i) => (
              <div key={i} className={`message ${msg.role}`}>
                <div className="message-content">{msg.content}</div>
                {msg.citations?.length > 0 && (
                  <div className="message-citations">
                    <small>引用: {msg.citations.map(c => `${c.heading} (${c.page_range})`).join(', ')}</small>
                  </div>
                )}
              </div>
            ))}
          </div>
          <div className="chat-input-sidebar">
            <textarea
              value={question}
              onChange={e => setQuestion(e.target.value)}
              placeholder="输入问题..."
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleAsk();
                }
              }}
            />
            <button onClick={handleAsk}>发送</button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default PaperReader;
