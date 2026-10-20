import axios from 'axios';

const API_BASE = '/api';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 120000,
});

let token = null;

// 模块加载时从 localStorage 恢复 token（React 子组件 effect 先于父组件执行，
// 若在 App 的 useEffect 里才 setToken，ReaderPage 的 getPapers 会先无 token 请求而 401）
try {
  const _saved = localStorage.getItem('token');
  if (_saved) {
    token = _saved;
    api.defaults.headers.common['Authorization'] = `Bearer ${_saved}`;
  }
} catch (_) {}

api.setToken = (t) => {
  token = t;
  if (t) {
    api.defaults.headers.common['Authorization'] = `Bearer ${t}`;
  } else {
    delete api.defaults.headers.common['Authorization'];
  }
};

api.login = (email, password) => api.post('/auth/login', { email, password });
api.getMe = () => api.get('/auth/me');

// Papers
api.getPapers = (params) => api.get('/papers', { params });
api.getPaper = (id) => api.get(`/papers/${id}`);
api.markRead = (id) => api.post(`/papers/${id}/read`);
api.uploadPaper = async (file, onProgress) => {
  const formData = new FormData();
  formData.append('file', file);
  return api.post('/papers/upload', formData, {
    onUploadProgress: onProgress,
  });
};
api.deletePaper = (id) => api.delete(`/papers/${id}`);
api.parsePaper = (id) => api.post(`/papers/${id}/parse`);

// Notes
api.getNotes = (paperId) => api.get(`/papers/${paperId}/notes`);
api.generateNotes = (paperId) => api.post(`/papers/${paperId}/notes/generate`);

// Reading Guide (AI 导读)
api.getReadingGuide = (paperId) => api.get(`/papers/${paperId}/reading-guide`);
api.generateReadingGuide = (paperId, force = false) => api.post(`/papers/${paperId}/reading-guide/generate`, { force });
api.saveEngagement = (paperId, data) => api.put(`/papers/${paperId}/reading-guide/engagement`, data);
api.exportEngagement = (paperId) => api.get(`/papers/${paperId}/reading-guide/engagement/export`);

// Chunks
api.searchChunks = (paperId, query, topK = 5) => api.post(`/papers/${paperId}/chunks/search`, { query, top_k: topK });
api.askQuestion = (paperId, question, sessionId, chatHistory = [], topK = 5) => {
  const headers = {};
  if (sessionId) headers['X-Session-ID'] = sessionId;
  return api.post(`/papers/${paperId}/chunks/qa`, {
    question,
    chat_history: chatHistory,
    top_k: topK,
  }, { headers });
};
api.getChunk = (paperId, chunkId) => api.get(`/papers/${paperId}/chunks/${chunkId}`);

// Fact Cards
api.getFactCards = (paperId) => api.get(`/papers/${paperId}/fact-cards`);
api.createFactCard = (paperId, card) => api.post(`/papers/${paperId}/fact-cards`, card);
api.updateFactCard = (paperId, factCardId, card) => api.put(`/papers/${paperId}/fact-cards/${factCardId}`, card);
api.deleteFactCard = (paperId, factCardId) => api.delete(`/papers/${paperId}/fact-cards/${factCardId}`);

// Sessions
api.getSessionMemory = (paperId, sessionId) => api.get(`/papers/${paperId}/sessions/${sessionId}/memory`);
api.addSessionMemory = (paperId, sessionId, turn) => api.post(`/papers/${paperId}/sessions/${sessionId}/memory`, turn);
api.clearSessionMemory = (paperId, sessionId) => api.delete(`/papers/${paperId}/sessions/${sessionId}/memory`);

// Market (GitHub 图书)
api.getMarketBooks = (refresh = false) => api.get('/market/books', { params: refresh ? { refresh: 1 } : {} });
api.importBook = (pdfPath, filename, source) => api.post('/market/import', { pdf_path: pdfPath, filename, source });

// Intensive Reading (精读训练)
api.getIntensiveArticles = (params) => api.get('/intensive/articles', { params });
api.getIntensiveArticle = (id) => api.get(`/intensive/articles/${id}`);
api.generateIntensiveGuide = (id) => api.post(`/intensive/articles/${id}/guide`);
api.scoreSummary = (id, keyPoints, summary) => api.post(`/intensive/articles/${id}/score`, { key_points: keyPoints, summary });

// Extensive Reading (泛读训练：新闻短文)
api.getExtensiveArticles = (params) => api.get('/extensive/articles', { params });
api.getExtensiveArticle = (id) => api.get(`/extensive/articles/${id}`);
api.generateExtensiveQuestions = (id) => api.post(`/extensive/articles/${id}/questions`);
api.scoreExtensive = (id, questions, answers) => api.post(`/extensive/articles/${id}/score`, { questions, answers });

// 已生成内容（持久化，不重复生成）
api.getGenerated = () => api.get('/generated');
api.getIntensiveGuide = (id) => api.get(`/intensive/articles/${id}/guide`);
api.getExtensiveQuestions = (id) => api.get(`/extensive/articles/${id}/questions`);

// Magazine (杂志书架：上传 → 拆分 → 评级入库)
api.getMagazines = () => api.get('/magazine');
api.getMagazine = (id) => api.get(`/magazine/${id}`);
api.uploadMagazine = async (file, onProgress) => {
  const formData = new FormData();
  formData.append('file', file);
  return api.post('/magazine/upload', formData, {
    onUploadProgress: onProgress,
    timeout: 120000,
  });
};
api.importMagazine = (id) => api.post(`/magazine/${id}/import`);
api.magazineToPaper = (id) => api.post(`/magazine/${id}/to-paper`);

// Reading log (读完记录)
api.markRead = (type, id) => api.post('/reading/mark-read', { type, id });
api.getReadLog = () => api.get('/reading');
api.getLevel = () => api.get('/reading/level');
api.getStats = () => api.get('/reading/stats');

export { api };
