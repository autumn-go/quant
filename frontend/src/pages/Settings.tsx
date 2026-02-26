import React from 'react';
import { Settings, Database, Bell, Shield, User } from 'lucide-react';
import './Settings.css';

const SettingsPage: React.FC = () => (
  <div className="settings">
    <div className="page-header">
      <h2>设置</h2>
      <p>系统配置 · 个人偏好</p>
    </div>

    <div className="settings-grid">
      <div className="setting-card glass-card">
        <div className="setting-icon"><User size={24} /></div>
        <div className="setting-info">
          <div className="setting-name">账户设置</div>
          <div className="setting-desc">修改个人信息和密码</div>
        </div>
      </div>

      <div className="setting-card glass-card">
        <div className="setting-icon"><Database size={24} /></div>
        <div className="setting-info">
          <div className="setting-name">数据源配置</div>
          <div className="setting-desc">AKShare API设置</div>
        </div>
      </div>

      <div className="setting-card glass-card">
        <div className="setting-icon"><Bell size={24} /></div>
        <div className="setting-info">
          <div className="setting-name">通知设置</div>
          <div className="setting-desc">信号提醒和推送</div>
        </div>
      </div>

      <div className="setting-card glass-card">
        <div className="setting-icon"><Shield size={24} /></div>
        <div className="setting-info">
          <div className="setting-name">安全设置</div>
          <div className="setting-desc">登录和权限管理</div>
        </div>
      </div>
    </div>
  </div>
);

export default SettingsPage;
