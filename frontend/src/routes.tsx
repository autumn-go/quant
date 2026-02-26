// 路由配置
import React from 'react';
import { Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import IndexMaster from './pages/IndexMaster';
import StyleMaster from './pages/StyleMaster';
import SectorRotation from './pages/SectorRotation';
import StockAnalysis from './pages/StockAnalysis';
import StrategyLib from './pages/StrategyLib';
import Backtest from './pages/Backtest';
import Settings from './pages/Settings';

const AppRoutes: React.FC = () => {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="index" element={<IndexMaster />} />
        <Route path="style" element={<StyleMaster />} />
        <Route path="sector" element={<SectorRotation />} />
        <Route path="stock" element={<StockAnalysis />} />
        <Route path="strategy" element={<StrategyLib />} />
        <Route path="backtest" element={<Backtest />} />
        <Route path="settings" element={<Settings />} />
      </Route>
    </Routes>
  );
};

export default AppRoutes;
