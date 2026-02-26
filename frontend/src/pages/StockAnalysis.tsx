import React, { useState } from 'react';
import { Search, TrendingUp, Activity, Clock, BarChart2 } from 'lucide-react';
import './StockAnalysis.css';

const subModules = [
  { id: 'trend', name: '趋势顶底', icon: TrendingUp, desc: '趋势判断与顶底识别' },
  { id: 'pattern', name: '形态学', icon: Activity, desc: 'K线形态与结构分析' },
  { id: 'intraday', name: '分时做T', icon: Clock, desc: '日内交易信号' },
  { id: 'oversold', name: '超跌透视', icon: BarChart2, desc: '超跌反弹机会' },
];

const StockAnalysis: React.FC = () => {
  const [activeTab, setActiveTab] = useState('trend');
  const [searchCode, setSearchCode] = useState('');

  return (
    <div className="stock-analysis">
      <div className="page-header">
        <h2>个股分析</h2>
        <p>多维度个股诊断 · 趋势/形态/做T</p>
      </div>

      {/* 搜索栏 */}
      <div className="search-bar glass-card">
        <Search size={20} />
        <input
          type="text"
          placeholder="输入股票代码或名称..."
          value={searchCode}
          onChange={(e) => setSearchCode(e.target.value)}
        />
        <button className="btn btn-primary">分析</button>
      </div>

      {/* 子模块标签 */}
      <div className="submodule-tabs">
        {subModules.map((mod) => {
          const Icon = mod.icon;
          return (
            <button
              key={mod.id}
              className={`submodule-tab ${activeTab === mod.id ? 'active' : ''}`}
              onClick={() => setActiveTab(mod.id)}
            >
              <Icon size={18} />
              <div className="tab-content">
                <span className="tab-name">{mod.name}</span>
                <span className="tab-desc">{mod.desc}</span>
              </div>
            </button>
          );
        })}
      </div>

      {/* 分析内容区 */}
      <div className="analysis-content glass-card">
        <div className="placeholder-content">
          <div className="placeholder-icon">
            {(() => {
              const Icon = subModules.find(m => m.id === activeTab)?.icon || TrendingUp;
              return <Icon size={48} />;
            })()}
          </div>
          <h3>{subModules.find(m => m.id === activeTab)?.name}</h3>
          <p>请输入股票代码开始分析</p>
        </div>
      </div>
    </div>
  );
};

export default StockAnalysis;
