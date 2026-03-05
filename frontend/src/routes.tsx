// 路由配置
import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './contexts/AuthContext';
import Layout from './components/Layout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import IndexMaster from './pages/IndexMaster';
import StyleMaster from './pages/StyleMaster';
import SectorRotation from './pages/SectorRotationV2';
import StockAnalysis from './pages/StockAnalysis';
import StrategyLib from './pages/StrategyLib';
import Backtest from './pages/Backtest';
import Settings from './pages/Settings';
import MarkdownDoc from './pages/MarkdownDoc';

// 受保护的路由组件
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated } = useAuth();
  
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  
  return <>{children}</>;
};

// 公开路由（已登录用户不能访问）
const PublicRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated } = useAuth();
  
  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }
  
  return <>{children}</>;
};

const AppRoutes: React.FC = () => {
  return (
    <Routes>
      {/* 登录页 */}
      <Route 
        path="/login" 
        element={
          <PublicRoute>
            <Login />
          </PublicRoute>
        } 
      />
      
      {/* 受保护的路由 */}
      <Route 
        path="/" 
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="index" element={<IndexMaster />} />
        <Route path="style" element={<StyleMaster />} />
        <Route path="sector" element={<SectorRotation />} />
        <Route path="doc/:filename" element={<MarkdownDoc />} />
        <Route path="stock" element={<StockAnalysis />} />
        <Route path="strategy" element={<StrategyLib />} />
        <Route path="backtest" element={<Backtest />} />
        <Route path="settings" element={<Settings />} />
      </Route>
      
      {/* 兜底路由 */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
};

export default AppRoutes;
