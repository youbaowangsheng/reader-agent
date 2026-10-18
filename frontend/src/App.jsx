import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router } from 'react-router-dom';
import { api } from './api/client';
import ShelfPage from './pages/ShelfPage';
import MarketPage from './pages/MarketPage';
import GuideIndexPage from './pages/GuideIndexPage';
import IntensivePage from './pages/IntensivePage';
import ExtensivePage from './pages/ExtensivePage';
import ReaderPage from './pages/ReaderPage';
import './App.css';

function App() {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [activeTab, setActiveTab] = useState('guide');
  const [openArticle, setOpenArticle] = useState(null);

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

  // 导读目录页点击文章 → 切到精读/泛读并打开指定文章
  const handleOpenArticle = (type, id) => {
    setOpenArticle({ type, id, nonce: Date.now() });
    setActiveTab(type);
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
          <GuideIndexPage active={activeTab === 'guide'} onOpenArticle={handleOpenArticle} />
          <IntensivePage
            active={activeTab === 'intensive'}
            openArticle={openArticle?.type === 'intensive' ? openArticle : null}
          />
          <ExtensivePage
            active={activeTab === 'extensive'}
            openArticle={openArticle?.type === 'extensive' ? openArticle : null}
          />
          <ReaderPage
            active={activeTab === 'papers'}
            openPaperId={openArticle?.type === 'papers' ? openArticle : null}
          />
          <ShelfPage active={activeTab === 'shelf'} onOpenPaper={() => {}} />
          <MarketPage active={activeTab === 'market'} onOpenPaper={() => {}} />
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
          Reader <span className="sub">AI 陪你精读每一篇</span>
        </div>
        <div className="nav-tabs">
          <button
            className={`nav-tab ${activeTab === 'guide' ? 'active' : ''}`}
            onClick={() => onTabChange('guide')}
          >首页导读</button>
          <button
            className={`nav-tab ${activeTab === 'intensive' ? 'active' : ''}`}
            onClick={() => onTabChange('intensive')}
          >AI精读</button>
          <button
            className={`nav-tab ${activeTab === 'extensive' ? 'active' : ''}`}
            onClick={() => onTabChange('extensive')}
          >AI泛读</button>
          <button
            className={`nav-tab ${activeTab === 'papers' ? 'active' : ''}`}
            onClick={() => onTabChange('papers')}
          >原文阅读</button>
          <button
            className={`nav-tab ${activeTab === 'shelf' ? 'active' : ''}`}
            onClick={() => onTabChange('shelf')}
          >我的书架</button>
          <button
            className={`nav-tab ${activeTab === 'market' ? 'active' : ''}`}
            onClick={() => onTabChange('market')}
          >图书市场</button>
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
        <p className="subtitle">AI 陪你精读每一篇</p>
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
