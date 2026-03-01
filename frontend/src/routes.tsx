// 路由配置
import React, { useEffect, useState } from 'react';
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import Layout from './components/Layout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import IndexMaster from './pages/IndexMaster';
import StyleMaster from './pages/StyleMaster';
import SectorRotation from './pages/SectorRotation';
import StockAnalysis from './pages/StockAnalysis';
import StrategyLib from './pages/StrategyLib';
import Backtest from './pages/Backtest';
import Settings from './pages/Settings';

// 受保护的路由组件
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const token = localStorage.getItem('quant_token');
    setIsAuthenticated(!!token);
  }, [navigate]);

  if (isAuthenticated === null) {
    return <div className="loading-screen">加载中...</div>;
  }

  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />;
};

const AppRoutes: React.FC = () => {
  return (
    <Routes>
      {/* 登录页面 - 公开访问 */}
      <Route path="/login" element={<Login />} />
      
      {/* 受保护的路由 */}
      <Route path="/" element={
        <ProtectedRoute>
          <Layout />
        </ProtectedRoute>
      }>
        <Route index element={<Dashboard />} />
        <Route path="index" element={<IndexMaster />} />
        <Route path="style" element={<StyleMaster />} />
        <Route path="sector" element={<SectorRotation />} />
        <Route path="stock" element={<StockAnalysis />} />
        <Route path="strategy" element={<StrategyLib />} />
        <Route path="backtest" element={<Backtest />} />
        <Route path="settings" element={<Settings />} />
      </Route>
      
      {/* 默认重定向 */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
};

export default AppRoutes;
