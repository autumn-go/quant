// 设置页面 - 包含多个子模块
import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { 
  Database, 
  Bell, 
  Shield, 
  User,
  ChevronRight,
  LogOut
} from 'lucide-react';
import AccountSettings from './settings/AccountSettings';
import './Settings.css';

type SettingsTab = 'account' | 'datasource' | 'notification' | 'security';

const SettingsPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<SettingsTab>('account');
  const { user, logout } = useAuth();

  const settingsMenu = [
    { id: 'account' as SettingsTab, icon: User, label: '账户管理', desc: '用户和权限' },
    { id: 'datasource' as SettingsTab, icon: Database, label: '数据源配置', desc: 'AKShare API设置' },
    { id: 'notification' as SettingsTab, icon: Bell, label: '通知设置', desc: '信号提醒和推送' },
    { id: 'security' as SettingsTab, icon: Shield, label: '安全设置', desc: '登录和权限管理' },
  ];

  const renderContent = () => {
    switch (activeTab) {
      case 'account':
        return <AccountSettings />;
      case 'datasource':
        return (
          <div className="settings-placeholder">
            <Database size={48} className="placeholder-icon" />
            <h3>数据源配置</h3>
            <p>AKShare API 设置功能开发中...</p>
          </div>
        );
      case 'notification':
        return (
          <div className="settings-placeholder">
            <Bell size={48} className="placeholder-icon" />
            <h3>通知设置</h3>
            <p>信号提醒和推送功能开发中...</p>
          </div>
        );
      case 'security':
        return (
          <div className="settings-placeholder">
            <Shield size={48} className="placeholder-icon" />
            <h3>安全设置</h3>
            <p>登录和权限管理功能开发中...</p>
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <div className="settings">
      {/* 页面标题 */}
      <div className="page-header">
        <h2>设置</h2>
        <p>系统配置 · 个人偏好</p>
      </div>

      <div className="settings-layout">
        {/* 左侧菜单 */}
        <div className="settings-sidebar">
          <div className="settings-menu">
            {settingsMenu.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              
              return (
                <button
                  key={item.id}
                  className={`settings-menu-item ${isActive ? 'active' : ''}`}
                  onClick={() => setActiveTab(item.id)}
                >
                  <div className="menu-item-icon">
                    <Icon size={20} />
                  </div>
                  <div className="menu-item-content">
                    <span className="menu-item-label">{item.label}</span>
                    <span className="menu-item-desc">{item.desc}</span>
                  </div>
                  <ChevronRight 
                    size={16} 
                    className={`menu-item-arrow ${isActive ? 'active' : ''}`}
                  />
                </button>
              );
            })}
          </div>

          {/* 用户信息卡片 */}
          <div className="user-card">
            <div className="user-card-avatar">
              {user?.username.charAt(0).toUpperCase()}
            </div>
            <div className="user-card-info">
              <span className="user-card-name">{user?.username}</span>
              <span className="user-card-role">
                {user?.isAdmin ? '管理员' : '普通用户'}
              </span>
            </div>
            <button className="btn-logout" onClick={logout} title="退出登录">
              <LogOut size={18} />
            </button>
          </div>
        </div>

        {/* 右侧内容区 */}
        <div className="settings-content">
          {renderContent()}
        </div>
      </div>
    </div>
  );
};

export default SettingsPage;
