import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router } from 'react-router-dom';
import { api } from './api/client';
import { initPush } from './api/push';
import ShelfPage from './pages/ShelfPage';
import MarketPage from './pages/MarketPage';
import GuideIndexPage from './pages/GuideIndexPage';
import IntensivePage from './pages/IntensivePage';
import ExtensivePage from './pages/ExtensivePage';
import ReaderPage from './pages/ReaderPage';
import './App.css';

// App 内（Capacitor WebView）用底部导航 + 两字标签；Web 保持顶部导航
const isNative = typeof window !== 'undefined' && window.Capacitor?.isNativePlatform?.();

const TABS = [
  { key: 'guide', label: '首页导读', short: '首页' },
  { key: 'intensive', label: 'AI精读', short: '精读' },
  { key: 'extensive', label: 'AI泛读', short: '泛读' },
  { key: 'papers', label: '原文阅读', short: '原文' },
  { key: 'shelf', label: '我的书架', short: '书架' },
  { key: 'market', label: '图书市场', short: '市场' },
];

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

  // App 内登录后注册推送（device token 上传后端）
  useEffect(() => {
    if (token) {
      initPush(api);
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
      <div className={`app-frame ${isNative ? 'native' : ''}`}>
        {!isNative && (
          <NavBar
            user={user}
            activeTab={activeTab}
            onTabChange={setActiveTab}
            onLogout={handleLogout}
          />
        )}
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
        {isNative && (
          <BottomNav activeTab={activeTab} onTabChange={setActiveTab} />
        )}
      </div>
    </Router>
  );
}

function NavBar({ user, activeTab, onTabChange, onLogout }) {
  return (
    <div className="nav-bar">
      <div className="nav-brand-row">
        <div className="logo">
          <span className="mark">R</span>
          <span>Reader</span>
        </div>
        <div className="nav-slogan">读得精 · 读得快 · 读得原味，AI 一路陪你</div>
        <div className="nav-right">
          <div className="user-avatar">
            {/^\d{11}$/.test(user?.email || '') ? user.email.slice(-2) : (user?.email?.[0]?.toUpperCase() || 'U')}
          </div>
          <button className="btn-ghost" onClick={onLogout}>退出</button>
        </div>
      </div>
      <div className="nav-tabs">
        {TABS.map(t => (
          <button
            key={t.key}
            className={`nav-tab ${activeTab === t.key ? 'active' : ''}`}
            onClick={() => onTabChange(t.key)}
          >{t.label}</button>
        ))}
      </div>
    </div>
  );
}

function BottomNav({ activeTab, onTabChange }) {
  return (
    <div className="bottom-nav">
      {TABS.map(t => (
        <button
          key={t.key}
          className={`bottom-tab ${activeTab === t.key ? 'active' : ''}`}
          onClick={() => onTabChange(t.key)}
        >{t.short}</button>
      ))}
    </div>
  );
}

function LoginPage({ onLogin }) {
  const [phone, setPhone] = useState('');
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [countdown, setCountdown] = useState(0);

  useEffect(() => {
    if (countdown <= 0) return;
    const t = setTimeout(() => setCountdown(c => c - 1), 1000);
    return () => clearTimeout(t);
  }, [countdown]);

  const handleSendCode = async () => {
    if (!/^1[3-9]\d{9}$/.test(phone)) {
      alert('请输入正确的手机号');
      return;
    }
    setSending(true);
    try {
      await api.sendCode(phone);
      setCountdown(60);
    } catch (err) {
      alert(err?.response?.data?.detail || '验证码发送失败');
    } finally {
      setSending(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!phone || !code) {
      alert('请输入手机号和验证码');
      return;
    }
    setLoading(true);
    try {
      const res = await api.login(phone, code);
      onLogin(res.data.token);
    } catch (err) {
      alert(err?.response?.data?.detail || '登录失败');
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
        <p className="subtitle">读得精 · 读得快 · 读得原味，AI 一路陪你</p>
        <form onSubmit={handleSubmit}>
          <input
            type="tel"
            placeholder="手机号"
            value={phone}
            onChange={e => setPhone(e.target.value)}
            maxLength={11}
          />
          <div className="code-row">
            <input
              type="text"
              placeholder="验证码"
              value={code}
              onChange={e => setCode(e.target.value)}
              maxLength={6}
            />
            <button
              type="button"
              className="btn-code"
              onClick={handleSendCode}
              disabled={sending || countdown > 0}
            >
              {countdown > 0 ? `${countdown}s` : '获取验证码'}
            </button>
          </div>
          <button type="submit" disabled={loading}>
            {loading ? '登录中…' : '登录'}
          </button>
        </form>
      </div>
    </div>
  );
}

export default App;
