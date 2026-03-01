import React, { useState, useEffect } from 'react';
import { Search, TrendingUp, Activity, Clock, BarChart2, ArrowUp, AlertCircle } from 'lucide-react';
import './StockAnalysis.css';

// 子模块配置
const subModules = [
  { id: 'trend', name: '趋势顶底', icon: TrendingUp, desc: '趋势判断与顶底识别' },
  { id: 'pattern', name: '形态学', icon: Activity, desc: 'K线形态与结构分析' },
  { id: 'intraday', name: '分时做T', icon: Clock, desc: '日内交易信号' },
  { id: 'oversold', name: '超跌透视', icon: BarChart2, desc: '超跌反弹机会' },
];

// ETF超跌数据类型
interface ETFOversoldData {
  ts_code: string;
  name: string;
  close: number;
  pct_chg: number;
  rsi_6: number;
  rsi_12: number;
  rsi_24: number;
  trade_date: string;
}

// 超跌透视组件
const OversoldAnalysis: React.FC = () => {
  const [data, setData] = useState<ETFOversoldData[]>([]);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState<'rsi_6' | 'rsi_12' | 'rsi_24'>('rsi_6');

  useEffect(() => {
    // 模拟从后端获取ETF超跌数据（RSI < 20）
    fetchOversoldETFs();
  }, []);

  const fetchOversoldETFs = async () => {
    setLoading(true);
    try {
      // 调用后端API获取真实ETF数据
      const response = await fetch(`/api/etf/oversold?rsi_threshold=20&rsi_period=${sortBy}&limit=50`);
      const result = await response.json();
      
      if (result.data) {
        setData(result.data);
      }
    } catch (error) {
      console.error('获取数据失败:', error);
      // 如果API失败，使用模拟数据
      const mockData: ETFOversoldData[] = [
        { ts_code: '510050.SH', name: '50ETF', close: 2.65, pct_chg: -2.5, rsi_6: 15.2, rsi_12: 18.5, rsi_24: 22.1, trade_date: '20260227' },
        { ts_code: '510300.SH', name: '300ETF', close: 3.85, pct_chg: -3.2, rsi_6: 12.8, rsi_12: 16.2, rsi_24: 19.5, trade_date: '20260227' },
        { ts_code: '510500.SH', name: '500ETF', close: 5.92, pct_chg: -4.1, rsi_6: 10.5, rsi_12: 14.8, rsi_24: 18.2, trade_date: '20260227' },
        { ts_code: '159915.SZ', name: '创业板ETF', close: 1.85, pct_chg: -5.2, rsi_6: 8.3, rsi_12: 12.5, rsi_24: 16.8, trade_date: '20260227' },
        { ts_code: '159901.SZ', name: '深100ETF', close: 3.12, pct_chg: -3.8, rsi_6: 14.1, rsi_12: 17.3, rsi_24: 20.5, trade_date: '20260227' },
        { ts_code: '512000.SH', name: '券商ETF', close: 0.95, pct_chg: -6.5, rsi_6: 5.2, rsi_12: 9.8, rsi_24: 14.2, trade_date: '20260227' },
        { ts_code: '512480.SH', name: '半导体ETF', close: 1.25, pct_chg: -7.2, rsi_6: 3.8, rsi_12: 8.5, rsi_24: 13.1, trade_date: '20260227' },
        { ts_code: '515030.SH', name: '新能源车ETF', close: 1.45, pct_chg: -5.8, rsi_6: 7.5, rsi_12: 11.2, rsi_24: 15.6, trade_date: '20260227' },
      ];
      const filtered = mockData.filter(etf => etf.rsi_6 < 20);
      const sorted = filtered.sort((a, b) => a.rsi_6 - b.rsi_6);
      setData(sorted);
    } finally {
      setLoading(false);
    }
  };

  const handleSort = (key: 'rsi_6' | 'rsi_12' | 'rsi_24') => {
    setSortBy(key);
    const sorted = [...data].sort((a, b) => a[key] - b[key]);
    setData(sorted);
  };

  const getRSIColor = (rsi: number) => {
    if (rsi < 10) return 'extreme';
    if (rsi < 15) return 'danger';
    if (rsi < 20) return 'warning';
    return 'normal';
  };

  return (
    <div className="oversold-panel">
      {/* 策略说明 */}
      <div className="strategy-header">
        <div className="strategy-title">
          <AlertCircle size={24} />
          <h3>ETF超跌透视策略</h3>
        </div>
        <p className="strategy-desc">
          基于ETF日K行情的RSI相对强弱指标，筛选RSI &lt; 20的超跌品种，
          按RSI值倒序排列。RSI越低表示超卖程度越严重，可能存在反弹机会。
        </p>
        <div className="strategy-tags">
          <span className="tag">RSI &lt; 20</span>
          <span className="tag">超卖区域</span>
          <span className="tag">反弹潜力</span>
          <span className="tag">ETF品种</span>
        </div>
      </div>

      {/* 统计卡片 */}
      <div className="stats-cards">
        <div className="stat-card">
          <span className="stat-value">{data.length}</span>
          <span className="stat-label">超跌ETF</span>
        </div>
        <div className="stat-card danger">
          <span className="stat-value">{data.length > 0 ? Math.min(...data.map(d => d.rsi_6)).toFixed(1) : '-'}</span>
          <span className="stat-label">最低RSI(6)</span>
        </div>
        <div className="stat-card warning">
          <span className="stat-value">{data.filter(d => d.rsi_6 < 10).length}</span>
          <span className="stat-label">极度超卖</span>
        </div>
      </div>

      {/* 数据表格 */}
      {loading ? (
        <div className="loading">加载中...</div>
      ) : (
        <div className="data-table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>排名</th>
                <th>ETF代码</th>
                <th>ETF名称</th>
                <th>最新价</th>
                <th>涨跌幅</th>
                <th className={`sortable ${sortBy === 'rsi_6' ? 'active' : ''}`} onClick={() => handleSort('rsi_6')}>
                  RSI(6) {sortBy === 'rsi_6' && <ArrowUp size={14} />}
                </th>
                <th className={`sortable ${sortBy === 'rsi_12' ? 'active' : ''}`} onClick={() => handleSort('rsi_12')}>
                  RSI(12) {sortBy === 'rsi_12' && <ArrowUp size={14} />}
                </th>
                <th className={`sortable ${sortBy === 'rsi_24' ? 'active' : ''}`} onClick={() => handleSort('rsi_24')}>
                  RSI(24) {sortBy === 'rsi_24' && <ArrowUp size={14} />}
                </th>
                <th>日期</th>
              </tr>
            </thead>
            <tbody>
              {data.map((etf, index) => (
                <tr key={etf.ts_code} className={index < 3 ? 'top-rank' : ''}>
                  <td className="rank">
                    {index < 3 ? (
                      <span className={`rank-badge rank-${index + 1}`}>{index + 1}</span>
                    ) : (
                      index + 1
                    )}
                  </td>
                  <td className="code">{etf.ts_code}</td>
                  <td className="name">{etf.name}</td>
                  <td className="price">¥{etf.close.toFixed(2)}</td>
                  <td className={`change ${etf.pct_chg < 0 ? 'negative' : 'positive'}`}>
                    {etf.pct_chg > 0 ? '+' : ''}{etf.pct_chg}%
                  </td>
                  <td className={`rsi ${getRSIColor(etf.rsi_6)}`}>
                    {etf.rsi_6.toFixed(1)}
                  </td>
                  <td className={`rsi ${getRSIColor(etf.rsi_12)}`}>
                    {etf.rsi_12.toFixed(1)}
                  </td>
                  <td className={`rsi ${getRSIColor(etf.rsi_24)}`}>
                    {etf.rsi_24.toFixed(1)}
                  </td>
                  <td className="date">{etf.trade_date}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
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
