import express from 'express';
import cors from 'cors';
import jwt from 'jsonwebtoken';
import { v4 as uuidv4 } from 'uuid';
import multer from 'multer';
import axios from 'axios';
import 'dotenv/config';

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(cors());
app.use(express.json());

// Configure multer for file uploads
const storage = multer.memoryStorage();
const upload = multer({ storage, limits: { fileSize: 50 * 1024 * 1024 } }); // 50MB limit

// JWT Secret
const isProduction = process.env.NODE_ENV === 'production';
const JWT_SECRET = process.env.JWT_SECRET || 'dev-only-secret-do-not-use-in-production';

if (isProduction && JWT_SECRET === 'dev-only-secret-do-not-use-in-production') {
  console.error('FATAL: JWT_SECRET environment variable is required in production');
  process.exit(1);
}

if (!process.env.JWT_SECRET) {
  console.warn('WARNING: Using default JWT_SECRET. Set JWT_SECRET environment variable in production.');
}

// Backend URL
const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8001';

// In-memory user store (replace with database in production)
const users = new Map();

// Demo user for testing (using valid UUID format)
const DEMO_USER_ID = '00000000-0000-0000-0000-000000000001';
users.set(DEMO_USER_ID, {
  id: DEMO_USER_ID,
  email: 'demo@example.com',
  name: 'Demo User'
});

// Simple JWT middleware
const authenticateToken = (req, res, next) => {
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1];

  if (!token) {
    return res.status(401).json({ error: 'Authentication required. Provide Bearer token.' });
  }

  try {
    const decoded = jwt.verify(token, JWT_SECRET);
    req.user = decoded;
    req.token = token;
    next();
  } catch (err) {
    if (err.name === 'TokenExpiredError') {
      return res.status(401).json({ error: 'Token expired' });
    }
    return res.status(401).json({ error: 'Invalid or expired token' });
  }
};

// Proxy helper
const proxyRequest = async (req, res, backendPath, options = {}) => {
  try {
    const headers = {
      'Content-Type': 'application/json',
      'X-User-ID': req.user.userId,
    };

    if (req.token) {
      headers['Authorization'] = `Bearer ${req.token}`;
    }

    const config = {
      method: options.method || 'GET',
      url: `${BACKEND_URL}${backendPath}`,
      headers,
      timeout: 120000,
    };

    if (options.method !== 'GET' && req.body) {
      config.data = req.body;
    }

    const response = await axios(config);
    res.status(response.status).json(response.data);
  } catch (error) {
    console.error(`Proxy error for ${backendPath}:`, error.message);
    if (error.response) {
      res.status(error.response.status).json(error.response.data);
    } else {
      res.status(502).json({ error: 'Backend service unavailable' });
    }
  }
};

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'healthy', service: 'reader-agent-gateway' });
});

// Auth routes
app.post('/api/auth/login', (req, res) => {
  const { email, password } = req.body;

  // Demo login - only allowed in development mode
  if (process.env.NODE_ENV === 'production') {
    return res.status(501).json({ error: 'Login not implemented in production. Use SSO/OAuth.' });
  }

  if (email && password) {
    const userId = uuidv4();
    const token = jwt.sign(
      { userId, email },
      JWT_SECRET,
      { expiresIn: '7d' }
    );

    users.set(userId, { id: userId, email, name: email.split('@')[0] });

    res.json({
      token,
      user: { id: userId, email, name: email.split('@')[0] }
    });
  } else {
    res.status(400).json({ error: 'Email and password required' });
  }
});

app.post('/api/auth/register', (req, res) => {
  const { email, password, name } = req.body;

  if (email && password) {
    const userId = uuidv4();
    const token = jwt.sign(
      { userId, email },
      JWT_SECRET,
      { expiresIn: '7d' }
    );

    users.set(userId, { id: userId, email, name: name || email.split('@')[0] });

    res.json({
      token,
      user: { id: userId, email, name: name || email.split('@')[0] }
    });
  } else {
    res.status(400).json({ error: 'Email and password required' });
  }
});

app.get('/api/auth/me', authenticateToken, (req, res) => {
  const user = users.get(req.user.userId);
  if (user) {
    res.json({ user });
  } else {
    res.json({ user: { id: req.user.userId, email: req.user.email } });
  }
});

// Papers routes
app.get('/api/papers', authenticateToken, async (req, res) => {
  await proxyRequest(req, res, '/api/papers');
});

app.get('/api/papers/:id', authenticateToken, async (req, res) => {
  await proxyRequest(req, res, `/api/papers/${req.params.id}`);
});

app.post('/api/papers/upload', authenticateToken, upload.single('file'), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'No file uploaded' });
    }

    const headers = {
      'X-User-ID': req.user.userId,
    };

    if (req.token) {
      headers['Authorization'] = `Bearer ${req.token}`;
    }

    // Use native fetch with FormData directly
    const formData = new FormData();

    // Create a Buffer from the file buffer if needed
    let buffer;
    if (Buffer.isBuffer(req.file.buffer)) {
      buffer = req.file.buffer;
    } else if (req.file.buffer instanceof Uint8Array) {
      buffer = Buffer.from(req.file.buffer);
    } else {
      buffer = Buffer.from(req.file.buffer);
    }

    // Create Blob and append to FormData
    const blob = new Blob([buffer], { type: req.file.mimetype || 'application/octet-stream' });
    formData.append('file', blob, req.file.originalname || 'file');

    // Use native fetch instead of axios
    const response = await fetch(`${BACKEND_URL}/api/papers/upload`, {
      method: 'POST',
      headers,
      body: formData,
    });

    const data = await response.json();
    res.status(response.status).json(data);
  } catch (error) {
    console.error('Upload error:', error.message);
    res.status(502).json({ error: 'Upload failed: ' + error.message });
  }
});

app.delete('/api/papers/:id', authenticateToken, async (req, res) => {
  await proxyRequest(req, res, `/api/papers/${req.params.id}`, { method: 'DELETE' });
});

app.post('/api/papers/:id/parse', authenticateToken, async (req, res) => {
  await proxyRequest(req, res, `/api/papers/${req.params.id}/parse`, { method: 'POST' });
});

// Notes routes
app.get('/api/papers/:id/notes', authenticateToken, async (req, res) => {
  await proxyRequest(req, res, `/api/papers/${req.params.id}/notes`);
});

app.post('/api/papers/:id/notes/generate', authenticateToken, async (req, res) => {
  await proxyRequest(req, res, `/api/papers/${req.params.id}/notes/generate`, {
    method: 'POST',
  });
});

// Chunks routes
app.post('/api/papers/:id/chunks/search', authenticateToken, async (req, res) => {
  await proxyRequest(req, res, `/api/papers/${req.params.id}/chunks/search`, {
    method: 'POST',
  });
});

app.post('/api/papers/:id/chunks/qa', authenticateToken, async (req, res) => {
  // Add session ID from header
  const sessionId = req.headers['x-session-id'];
  const body = { ...req.body, sessionId };
  const originalSend = res.status.bind(res);
  const originalJson = res.json.bind(res);

  try {
    const headers = {
      'Content-Type': 'application/json',
      'X-User-ID': req.user.userId,
      'X-Session-ID': sessionId || uuidv4(),
    };

    if (req.token) {
      headers['Authorization'] = `Bearer ${req.token}`;
    }

    const response = await axios.post(
      `${BACKEND_URL}/api/papers/${req.params.id}/chunks/qa`,
      body,
      { headers }
    );

    res.status(response.status).json(response.data);
  } catch (error) {
    console.error('QA error:', error.message);
    if (error.response) {
      res.status(error.response.status).json(error.response.data);
    } else {
      res.status(502).json({ error: 'QA service unavailable' });
    }
  }
});

app.get('/api/papers/:id/chunks/:chunkId', authenticateToken, async (req, res) => {
  await proxyRequest(req, res, `/api/papers/${req.params.id}/chunks/${req.params.chunkId}`);
});

// Fact cards routes
app.get('/api/papers/:id/fact-cards', authenticateToken, async (req, res) => {
  await proxyRequest(req, res, `/api/papers/${req.params.id}/fact-cards`);
});

app.post('/api/papers/:id/fact-cards', authenticateToken, async (req, res) => {
  await proxyRequest(req, res, `/api/papers/${req.params.id}/fact-cards`, {
    method: 'POST',
  });
});

app.put('/api/papers/:id/fact-cards/:factCardId', authenticateToken, async (req, res) => {
  await proxyRequest(req, res, `/api/papers/${req.params.id}/fact-cards/${req.params.factCardId}`, {
    method: 'PUT',
  });
});

app.delete('/api/papers/:id/fact-cards/:factCardId', authenticateToken, async (req, res) => {
  await proxyRequest(req, res, `/api/papers/${req.params.id}/fact-cards/${req.params.factCardId}`, {
    method: 'DELETE',
  });
});

// Sessions routes
app.get('/api/papers/:id/sessions/:sessionId/memory', authenticateToken, async (req, res) => {
  await proxyRequest(req, res, `/api/papers/${req.params.id}/sessions/${req.params.sessionId}/memory`);
});

app.post('/api/papers/:id/sessions/:sessionId/memory', authenticateToken, async (req, res) => {
  await proxyRequest(req, res, `/api/papers/${req.params.id}/sessions/${req.params.sessionId}/memory`, {
    method: 'POST',
  });
});

app.delete('/api/papers/:id/sessions/:sessionId/memory', authenticateToken, async (req, res) => {
  await proxyRequest(req, res, `/api/papers/${req.params.id}/sessions/${req.params.sessionId}/memory`, {
    method: 'DELETE',
  });
});

// Error handling middleware
app.use((err, req, res, next) => {
  console.error('Gateway error:', err);
  res.status(500).json({ error: 'Internal gateway error' });
});

app.listen(PORT, () => {
  console.log(`Reader Agent Gateway running on port ${PORT}`);
  console.log(`Backend URL: ${BACKEND_URL}`);
});

export default app;