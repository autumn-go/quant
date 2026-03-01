import React, { useState, useEffect } from 'react';
import { Search, TrendingUp, Activity, Clock, BarChart2, ArrowDown, ArrowUp, TrendingDown } from 'lucide-react';
import './StockAnalysis.css';

// 子模块配置
const subModules = [
  { id: 'trend', name: '趋势顶底', icon: TrendingUp, desc: '趋势判断与顶底识别' },
  { id: 'pattern', name: '形态学', icon: Activity, desc: 'K线形态与结构分析' },
  { id: 'intraday', name: '分时做T', icon: Clock, desc: '日内交易信号' },
  { id: 'oversold', name: '超跌透视', icon: BarChart2, desc: '超跌反弹机会' },
];

// 模拟超跌数据 (RSI < 20)
const mockOversoldData = [
  { code: '000001.SZ', name: '平安银行', price: 9.85, change: -5.2, rsi: 18.5, volume: '12.5亿', days: 5 },
  { code: '000002.SZ', name: '万科A', price: 15.32, change: -4.8, rsi: 16.2, volume: '8.3亿', days: 7 },
  { code: '600519.SH', name: '贵州茅台', price: 1580.0, change: -3.5, rsi: 19.1, volume: '25.6亿', days: 3 },
  { code: '000858.SZ', name: '五粮液', price: 128.5, change: -6.1, rsi: 15.8, volume: '15.2亿', days: 8 },
  { code: '002415.SZ', name: '海康威视', price: 32.18, change: -4.2, rsi: 17.3, volume: '6.8亿', days: 4 },
  { code: '600036.SH', name: '招商银行', price: 32.5, change: -3.9, rsi: 19.8, volume: '18.5亿', days: 6 },
  { code: '000333.SZ', name: '美的集团', price: 58.2, change: -5.5, rsi: 14.2, volume: '9.2亿', days: 9 },
  { code: '002594.SZ', name: '比亚迪', price: 198.5, change: -7.2, rsi: 12.5, volume: '32.1亿', days: 11 },
  { code: '600276.SH', name: '恒瑞医药', price: 42.8, change: -4.5, rsi: 18.9, volume: '11.3亿', days: 5 },
  { code: '300750.SZ', name: '宁德时代', price: 185.6, change: -6.8, rsi: 13.7, volume: '28.5亿', days: 10 },
];

// 超跌透视组件
const OversoldAnalysis: React.FC = () => {
  const [data, setData] = useState(mockOversoldData);
  const [sortBy, setSortBy] = useState<'rsi' | 'change' | 'days'>('rsi');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');

  // 排序逻辑
  const sortedData = [...data].sort((a, b) => {
    const factor = sortOrder === 'asc' ? 1 : -1;
    return (a[sortBy] - b[sortBy]) * factor;
  });

  const handleSort = (key: 'rsi' | 'change' | 'days') => {
    if (sortBy === key) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(key);
      setSortOrder('asc');
    }
  };

  return (
    <div className="oversold-panel">
      {/* 统计卡片 */}
      <div className="stats-cards">
        <div className="stat-card">
          <div className="stat-icon">
            <TrendingDown size={24} />
          </div>
          <div className="stat-info">
            <span className="stat-value">{data.length}</span>
            <span className="stat-label">超跌标的</span>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon warning">
            <Activity size={24} />
          </div>
          <div className="stat-info">
            <span className="stat-value">{Math.min(...data.map(d => d.rsi)).toFixed(1)}</span>
            <span className="stat-label">最低RSI</span>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon danger">
            <ArrowDown size={24} />
          </div>
          <div className="stat-info">
            <span className="stat-value">{Math.min(...data.map(d => d.change)).toFixed(1)}%</span>
            <span className="stat-label">最大跌幅</span>
          </div>
        </div>
      </div>

      {/* 策略说明 */}
      <div className="strategy-info">
        <h4>📊 超跌透视策略</h4>
        <p>基于 RSI 相对强弱指标，筛选 RSI &lt; 20 的超跌股票，按 RSI 值倒序排列。RSI 越低表示超卖程度越严重，可能存在反弹机会。</p>
        <div className="strategy-tags">
          <span className="tag">RSI &lt; 20</span>
          <span className="tag">超卖区域</span>
          <span className="tag">反弹潜力</span>
        </div>
      </div>

      {/* 数据表格 */}
      <div className="data-table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>排名</th>
              <th>股票代码</th>
              <th>股票名称</th>
              <th>最新价</th>
              <th className="sortable" onClick={() => handleSort('change')}>
                涨跌幅 {sortBy === 'change' && (sortOrder === 'asc' ? <ArrowUp size={14}/> : <ArrowDown size={14}/>)}
              </th>
              <th className="sortable" onClick={() => handleSort('rsi')}>
                RSI(14) {sortBy === 'rsi' && (sortOrder === 'asc' ? <ArrowUp size={14}/> : <ArrowDown size={14}/>)}
              </th>
              <th>成交额</th>
              <th className="sortable" onClick={() => handleSort('days')}>
                连续下跌 {sortBy === 'days' && (sortOrder === 'asc' ? <ArrowUp size={14}/> : <ArrowDown size={14}/>)}
              </th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {sortedData.map((stock, index) => (
              <tr key={stock.code} className={index < 3 ? 'top-rank' : ''}>
                <td className="rank">
                  {index < 3 ? (
                    <span className={`rank-badge rank-${index + 1}`}>{index + 1}</span>
                  ) : (
                    index + 1
                  )}
                </td>
                <td className="code">{stock.code}</td>
                <td className="name">{stock.name}</td>
                <td className="price">¥{stock.price.toFixed(2)}</td>
                <td className={`change ${stock.change < 0 ? 'negative' : 'positive'}`}>
                  {stock.change > 0 ? '+' : ''}{stock.change}%
                </td>
                <td className={`rsi ${stock.rsi < 15 ? 'extreme' : stock.rsi < 20 ? 'high' : ''}`}>
                  {stock.rsi}
                </td>
                <td className="volume">{stock.volume}</td>
                <td className="days">
                  <span className="days-badge">{stock.days}天</span>
                </td>
                <td>
                  <button className="btn-analyze">分析</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// 其他模块的占位组件
const PlaceholderModule: React.FC<{ name: string; desc: string }> = ({ name, desc }) => (
  <div className="placeholder-module">
    <div className="placeholder-icon-large">
      <Activity size={64} />
    </div>
    <h3>{name}</h3>
    <p>{desc}</p>
    <div className="coming-soon">功能开发中...</div>
  </div>
);

const StockAnalysis: React.FC = () => {
  const [activeTab, setActiveTab] = useState('oversold'); // 默认显示超跌透视
  const [searchCode, setSearchCode] = useState('');

  const activeModule = subModules.find(m => m.id === activeTab);

  return (
    <div className="stock-analysis">
      <div className="page-header">
        <h2>个股分析</h2>
        <p>多维度个股诊断 · 趋势/形态/做T/超跌</p>
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
        {activeTab === 'oversold' ? (
          <OversoldAnalysis />
        ) : (
          <PlaceholderModule 
            name={activeModule?.name || ''} 
            desc={activeModule?.desc || ''} 
          />
        )}
      </div>
    </div>
  );
};

export default StockAnalysis;
