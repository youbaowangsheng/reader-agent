import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, useNavigate } from 'react-router-dom';
import { api } from './api/client';
import ShelfPage from './pages/ShelfPage';
import MarketPage from './pages/MarketPage';
import ReaderPage from './pages/ReaderPage';
import './App.css';

function App() {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [activeTab, setActiveTab] = useState('reader');

  useEffect(() => {
    if (token) {
      api.setToken(token);
      api.getMe().then(res => {
        setUser(res.data.user);
      }).catch(() => {
        localStorage.removeItem('token');
        setToken(null);
      });
    }
  }, [token]);

  const handleLogin = (newToken) => {
    localStorage.setItem('token', newToken);
    setToken(newToken);
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    setToken(null);
  };

  if (!token) {
    return <LoginPage onLogin={handleLogin} />;
  }

  return (
    <Router>
      <div className="app-frame">
        <NavBar
          user={user}
          activeTab={activeTab}
          onTabChange={setActiveTab}
          onLogout={handleLogout}
        />
        <div className="content">
          <ShelfPage active={activeTab === 'shelf'} />
          <MarketPage active={activeTab === 'market'} />
          <ReaderPage active={activeTab === 'reader'} />
        </div>
      </div>
    </Router>
  );
}

function NavBar({ user, activeTab, onTabChange, onLogout }) {
  return (
    <div className="nav-bar">
      <div className="nav-left">
        <div className="logo">
          <span className="mark">R</span>
          Reader <span className="sub">AI 导读</span>
        </div>
        <div className="nav-tabs">
          <button
            className={`nav-tab ${activeTab === 'reader' ? 'active' : ''}`}
            onClick={() => onTabChange('reader')}
          >导读</button>
          <button
            className={`nav-tab ${activeTab === 'shelf' ? 'active' : ''}`}
            onClick={() => onTabChange('shelf')}
          >书架</button>
          <button
            className={`nav-tab ${activeTab === 'market' ? 'active' : ''}`}
            onClick={() => onTabChange('market')}
          >市场</button>
        </div>
      </div>
      <div className="nav-right">
        <div className="user-avatar">{user?.email?.[0]?.toUpperCase() || 'U'}</div>
        <button className="btn-ghost" onClick={onLogout}>退出</button>
      </div>
    </div>
  );
}

function LoginPage({ onLogin }) {
  const [email, setEmail] = useState('demo@example.com');
  const [password, setPassword] = useState('demo');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await api.login(email, password);
      onLogin(res.data.token);
    } catch (err) {
      alert('登录失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="brand">
          <span className="logo">R</span>
          Reader Agent
        </div>
        <p className="subtitle">英文论文阅读助手</p>
        <form onSubmit={handleSubmit}>
          <input
            type="email"
            placeholder="邮箱"
            value={email}
            onChange={e => setEmail(e.target.value)}
          />
          <input
            type="password"
            placeholder="密码"
            value={password}
            onChange={e => setPassword(e.target.value)}
          />
          <button type="submit" disabled={loading}>
            {loading ? '登录中…' : '登录'}
          </button>
        </form>
      </div>
    </div>
  );
}

export default App;
