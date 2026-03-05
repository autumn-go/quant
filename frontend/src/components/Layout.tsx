// 布局组件 - 侧边栏 + 主内容区
import React, { useState } from 'react';
import { Outlet, NavLink, useLocation } from 'react-router-dom';
import { 
  LayoutDashboard, 
  TrendingUp, 
  PieChart, 
  RotateCcw, 
  BarChart3, 
  BookOpen, 
  TestTube, 
  Settings,
  Menu,
  X,
  Zap,
  ChevronRight,
  LogOut,
  Shield
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import './Layout.css';

const menuItems = [
  { path: '/', icon: LayoutDashboard, label: '总览', desc: 'Dashboard' },
  { path: '/index', icon: TrendingUp, label: '指数大师', desc: '指数择时' },
  { path: '/style', icon: PieChart, label: '宽基大师', desc: '风格择时' },
  { path: '/sector', icon: RotateCcw, label: '板块轮动 Pro', desc: 'K-Means聚类+阻力打分' },
  { path: '/stock', icon: BarChart3, label: '个股分析', desc: '趋势/形态/做T' },
  { path: '/strategy', icon: BookOpen, label: '策略库', desc: '策略管理' },
  { path: '/backtest', icon: TestTube, label: '回测中心', desc: '策略验证' },
  { path: '/settings', icon: Settings, label: '设置', desc: '系统配置' },
];

const Layout: React.FC = () => {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();
  const { user, logout } = useAuth();

  return (
    <div className="layout">
      {/* 移动端遮罩 */}
      {mobileOpen && (
        <div 
          className="mobile-overlay" 
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* 侧边栏 */}
      <aside className={`sidebar ${collapsed ? 'collapsed' : ''} ${mobileOpen ? 'mobile-open' : ''}`}>
        {/* Logo区域 */}
        <div className="sidebar-header">
          <div className="logo">
            <Zap className="logo-icon" />
            {!collapsed && (
              <div className="logo-text">
                <span className="logo-title">QuantPro</span>
                <span className="logo-subtitle">投研系统</span>
              </div>
            )}
          </div>
          <button 
            className="collapse-btn hide-mobile"
            onClick={() => setCollapsed(!collapsed)}
          >
            <ChevronRight className={`collapse-icon ${collapsed ? 'rotated' : ''}`} />
          </button>
          <button 
            className="mobile-close show-mobile"
            onClick={() => setMobileOpen(false)}
          >
            <X size={20} />
          </button>
        </div>

        {/* 导航菜单 */}
        <nav className="sidebar-nav">
          {menuItems.map((item, index) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            
            return (
              <NavLink
                key={item.path}
                to={item.path}
                className={`nav-item ${isActive ? 'active' : ''}`}
                style={{ animationDelay: `${index * 0.05}s` }}
                onClick={() => setMobileOpen(false)}
              >
                <div className="nav-icon-wrapper">
                  <Icon className="nav-icon" size={20} />
                  {isActive && <div className="nav-indicator" />}
                </div>
                {!collapsed && (
                  <div className="nav-content">
                    <span className="nav-label">{item.label}</span>
                    <span className="nav-desc">{item.desc}</span>
                  </div>
                )}
              </NavLink>
            );
          })}
        </nav>

        {/* 底部信息 */}
        {!collapsed && (
          <div className="sidebar-footer">
            <div className="system-status">
              <div className="status-dot" />
              <span>系统运行正常</span>
            </div>            <div className="version">
              v1.0.0
            </div>
          </div>
        )}
      </aside>

      {/* 主内容区 */}
      <main className="main-content">
        {/* 顶部栏 */}
        <header className="top-bar">
          <button 
            className="mobile-menu-btn show-mobile"
            onClick={() => setMobileOpen(true)}
          >
            <Menu size={20} />
          </button>
          
          <div className="breadcrumb">
            {menuItems.find(item => item.path === location.pathname)?.label || '总览'}
          </div>

          <div className="top-actions">
            <div className="market-status">
              <span className="market-badge">A股交易中</span>
            </div>
            <div className="user-info">
              <div className="user-avatar" title={user?.username}>
                {user?.isAdmin ? <Shield size={16} /> : user?.username.charAt(0).toUpperCase()}
              </div>
              <button className="logout-btn" onClick={logout} title="退出登录">
                <LogOut size={18} />
              </button>
            </div>
          </div>
        </header>

        {/* 页面内容 */}
        <div className="page-content">
          <Outlet />
        </div>
      </main>
    </div>
  );
};

export default Layout;
