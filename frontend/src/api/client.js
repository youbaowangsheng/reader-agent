import axios from 'axios';

const API_BASE = '/api';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 120000,
});

let token = null;

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
api.getPapers = () => api.get('/papers');
api.getPaper = (id) => api.get(`/papers/${id}`);
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
api.getMarketBooks = () => api.get('/market/books');
api.importBook = (pdfPath, filename) => api.post('/market/import', { pdf_path: pdfPath, filename });

export { api };
