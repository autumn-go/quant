// 登录页面
import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Zap, Eye, EyeOff, Lock, User } from 'lucide-react';
import './Login.css';

const Login: React.FC = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  
  const { login } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const success = await login(username, password);
      if (!success) {
        setError('用户名或密码错误');
      }
    } catch (err) {
      setError('登录失败，请重试');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-container">
        {/* Logo区域 */}
        <div className="login-header">
          <div className="login-logo">
            <Zap size={40} className="logo-icon" />
          </div>
          <h1>QuantPro</h1>
          <p>投研系统</p>
        </div>

        {/* 登录表单 */}
        <form onSubmit={handleSubmit} className="login-form">
          {error && (
            <div className="login-error">
              {error}
            </div>
          )}

          <div className="login-field">
            <label>
              <User size={18} />
              用户名
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="请输入用户名"
              required
              autoFocus
            />
          </div>

          <div className="login-field">
            <label>
              <Lock size={18} />
              密码
            </label>
            <div className="password-input-wrapper">
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="请输入密码"
                required
              />
              <button
                type="button"
                className="toggle-password"
                onClick={() => setShowPassword(!showPassword)}
              >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            className="login-button"
            disabled={isLoading || !username || !password}
          >
            {isLoading ? (
              <span className="loading-spinner" />
            ) : (
              '登录'
            )}
          </button>
        </form>

        {/* 底部提示 */}
        <div className="login-footer">
          <p>默认账户: admin / admin123</p>
        </div>
      </div>

      {/* 背景装饰 */}
      <div className="login-bg-decoration">
        <div className="bg-circle circle-1" />
        <div className="bg-circle circle-2" />
        <div className="bg-circle circle-3" />
      </div>
    </div>
  );
};

export default Login;
