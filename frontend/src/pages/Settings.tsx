import React, { useState } from 'react';
import { Database, Bell, Shield, User, Lock, Mail, Key, Save, LogOut } from 'lucide-react';
import './Settings.css';

const SettingsPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState('account');
  const [passwordForm, setPasswordForm] = useState({
    current: '',
    new: '',
    confirm: ''
  });
  const [saved, setSaved] = useState(false);

  const handlePasswordChange = (e: React.FormEvent) => {
    e.preventDefault();
    // 模拟保存
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
    setPasswordForm({ current: '', new: '', confirm: '' });
  };

  const handleLogout = () => {
    localStorage.removeItem('quant_token');
    localStorage.removeItem('quant_user');
    window.location.href = '/login';
  };

  return (
    <div className="settings">
      <div className="page-header">
        <h2>设置</h2>
        <p>系统配置 · 个人偏好 · 账号管理</p>
      </div>

      <div className="settings-layout">
        {/* 左侧菜单 */}
        <div className="settings-sidebar">
          <button 
            className={`settings-menu-item ${activeTab === 'account' ? 'active' : ''}`}
            onClick={() => setActiveTab('account')}
          >
            <User size={20} />
            <span>账户设置</span>
          </button>
          
          <button 
            className={`settings-menu-item ${activeTab === 'password' ? 'active' : ''}`}
            onClick={() => setActiveTab('password')}
          >
            <Lock size={20} />
            <span>修改密码</span>
          </button>
          
          <button 
            className={`settings-menu-item ${activeTab === 'data' ? 'active' : ''}`}
            onClick={() => setActiveTab('data')}
          >
            <Database size={20} />
            <span>数据源配置</span>
          </button>
          
          <button 
            className={`settings-menu-item ${activeTab === 'notifications' ? 'active' : ''}`}
            onClick={() => setActiveTab('notifications')}
          >
            <Bell size={20} />
            <span>通知设置</span>
          </button>
          
          <button 
            className={`settings-menu-item ${activeTab === 'security' ? 'active' : ''}`}
            onClick={() => setActiveTab('security')}
          >
            <Shield size={20} />
            <span>安全设置</span>
          </button>

          <div className="settings-divider" />

          <button className="settings-menu-item logout" onClick={handleLogout}>
            <LogOut size={20} />
            <span>退出登录</span>
          </button>
        </div>

        {/* 右侧内容 */}
        <div className="settings-content glass-card">
          {/* 账户设置 */}
          {activeTab === 'account' && (
            <div className="settings-section">
              <h3><User size={24} /> 账户信息</h3>
              
              <div className="form-group">
                <label>用户名</label>
                <input type="text" defaultValue="admin" />
              </div>
              
              <div className="form-group">
                <label>邮箱</label>
                <div className="input-with-icon">
                  <Mail size={18} />
                  <input type="email" placeholder="请输入邮箱" />
                </div>
              </div>
              
              <div className="form-group">
                <label>手机号</label>
                <input type="tel" placeholder="请输入手机号" />
              </div>
              
              <button className="btn-save">
                <Save size={18} /> 保存修改
              </button>
            </div>
          )}

          {/* 修改密码 */}
          {activeTab === 'password' && (
            <div className="settings-section">
              <h3><Key size={24} /> 修改密码</h3>
              
              {saved && <div className="save-success">密码修改成功！</div>}
              
              <form onSubmit={handlePasswordChange}>
                <div className="form-group">
                  <label>当前密码</label>
                  <input 
                    type="password" 
                    value={passwordForm.current}
                    onChange={(e) => setPasswordForm({...passwordForm, current: e.target.value})}
                    placeholder="请输入当前密码"
                    required
                  />
                </div>
                
                <div className="form-group">
                  <label>新密码</label>
                  <input 
                    type="password"
                    value={passwordForm.new}
                    onChange={(e) => setPasswordForm({...passwordForm, new: e.target.value})}
                    placeholder="请输入新密码（至少6位）"
                    required
                    minLength={6}
                  />
                </div>
                
                <div className="form-group">
                  <label>确认新密码</label>
                  <input 
                    type="password"
                    value={passwordForm.confirm}
                    onChange={(e) => setPasswordForm({...passwordForm, confirm: e.target.value})}
                    placeholder="请再次输入新密码"
                    required
                  />
                </div>
                
                <button type="submit" className="btn-save">
                  <Lock size={18} /> 修改密码
                </button>
              </form>
            </div>
          )}

          {/* 数据源配置 */}
          {activeTab === 'data' && (
            <div className="settings-section">
              <h3><Database size={24} /> 数据源配置</h3>
              
              <div className="form-group">
                <label>Tushare Token</label>
                <input type="password" placeholder="请输入Tushare API Token" />
              </div>
              
              <div className="form-group">
                <label>数据更新频率</label>
                <select>
                  <option>实时</option>
                  <option selected>每日收盘后</option>
                  <option>手动更新</option>
                </select>
              </div>
              
              <button className="btn-save"><Save size={18} /> 保存配置</button>
            </div>
          )}

          {/* 通知设置 */}
          {activeTab === 'notifications' && (
            <div className="settings-section">
              <h3><Bell size={24} /> 通知设置</h3>
              
              <div className="toggle-list">
                <label className="toggle-item">
                  <span>交易信号提醒</span>
                  <input type="checkbox" defaultChecked />
                </label>
                
                <label className="toggle-item">
                  <span>策略执行通知</span>
                  <input type="checkbox" defaultChecked />
                </label>
                
                <label className="toggle-item">
                  <span>系统公告</span>
                  <input type="checkbox" />
                </label>
              </div>
            </div>
          )}

          {/* 安全设置 */}
          {activeTab === 'security' && (
            <div className="settings-section">
              <h3><Shield size={24} /> 安全设置</h3>
              
              <div className="toggle-list">
                <label className="toggle-item">
                  <span>登录二次验证</span>
                  <input type="checkbox" />
                </label>
                
                <label className="toggle-item">
                  <span>异地登录提醒</span>
                  <input type="checkbox" defaultChecked />
                </label>
              </div>
              
              <div className="security-info">
                <p>上次登录：2026-03-01 14:30:00</p>
                <p>登录IP：192.168.1.100</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default SettingsPage;
