import React, { useState, useEffect } from 'react';
import { Search, TrendingUp, Activity, Clock, BarChart2, ArrowUp, AlertCircle, ChevronLeft, ChevronRight, RefreshCw } from 'lucide-react';
import './StockAnalysis.css';

const subModules = [
  { id: 'trend', name: '趋势顶底', icon: TrendingUp, desc: '趋势判断与顶底识别' },
  { id: 'pattern', name: '形态学', icon: Activity, desc: 'K线形态与结构分析' },
  { id: 'intraday', name: '分时做T', icon: Clock, desc: '日内交易信号' },
  { id: 'oversold', name: '超跌透视', icon: BarChart2, desc: '超跌反弹机会' },
];

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

const getTodayStr = () => {
  const now = new Date();
  return `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}`;
};

const getLastTradeDate = () => {
  const now = new Date();
  const day = now.getDay();
  if (day === 0) now.setDate(now.getDate() - 2);
  else if (day === 6) now.setDate(now.getDate() - 1);
  return `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}`;
};

const OversoldAnalysis: React.FC = () => {
  const [allData, setAllData] = useState<ETFOversoldData[]>([]);
  const [displayData, setDisplayData] = useState<ETFOversoldData[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dataDate, setDataDate] = useState<string>('');
  const [isLatest, setIsLatest] = useState<boolean>(true);
  const [sortBy, setSortBy] = useState<'rsi_6' | 'rsi_12' | 'rsi_24'>('rsi_6');
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 10;

  useEffect(() => { fetchOversoldETFs(); }, []);
  useEffect(() => {
    const sorted = [...allData].sort((a, b) => a[sortBy] - b[sortBy]);
    const start = (currentPage - 1) * pageSize;
    setDisplayData(sorted.slice(start, start + pageSize));
  }, [allData, sortBy, currentPage]);

  const fetchOversoldETFs = async () => {
    setLoading(true); setError(null);
    try {
      const res = await fetch('/etf_oversold.json?t=' + Date.now());
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const result = await res.json();
      if (result.data?.length > 0) {
        const filtered = result.data.filter((e: ETFOversoldData) => e.rsi_6 != null && e.rsi_6 < 20);
        setAllData(filtered.sort((a: ETFOversoldData, b: ETFOversoldData) => a.rsi_6 - b.rsi_6));
        setCurrentPage(1);
        const latestDate = result.data[0]?.trade_date || '';
        setDataDate(latestDate);
        setIsLatest(latestDate === getTodayStr() || latestDate === getLastTradeDate());
      } else {
        setAllData([]); setError('暂无超跌ETF数据');
      }
    } catch (e) {
      setError(`获取数据失败: ${e instanceof Error ? e.message : '未知错误'}`); setAllData([]);
    } finally { setLoading(false); }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    if (isLatest) {
      await fetchOversoldETFs();
    } else {
      setError('数据更新需要在服务端执行，请联系管理员更新数据');
    }
    setRefreshing(false);
  };

  const handleSort = (key: 'rsi_6' | 'rsi_12' | 'rsi_24') => { setSortBy(key); setCurrentPage(1); };
  const getRSIColor = (rsi: number) => rsi < 10 ? 'extreme' : rsi < 15 ? 'danger' : rsi < 20 ? 'warning' : 'normal';
  const totalPages = Math.ceil(allData.length / pageSize);

  return (
    <div className="oversold-panel">
      <div className="strategy-header">
        <div className="strategy-title"><AlertCircle size={24} /><h3>ETF超跌透视策略</h3></div>
        <div className="header-actions">
          <span className="data-date">数据日期: {dataDate || '-'}</span>
          <button className={`refresh-btn ${refreshing ? 'spinning' : ''} ${!isLatest ? 'needs-update' : ''}`} onClick={handleRefresh} disabled={refreshing}>
            <RefreshCw size={18} />{refreshing ? '刷新中...' : '刷新'}
          </button>
        </div>
      </div>
      
      <p className="strategy-desc">基于ETF日K行情的RSI相对强弱指标，筛选RSI6 &lt; 20的超跌品种。</p>
      <div className="strategy-tags">
        <span className="tag">RSI6 &lt; 20</span><span className="tag">超卖区域</span><span className="tag">反弹潜力</span>
        {!isLatest && <span className="tag warning">数据需更新</span>}
      </div>

      <div className="stats-cards">
        <div className="stat-card"><span className="stat-value">{allData.length}</span><span className="stat-label">超跌ETF</span></div>
        <div className="stat-card danger"><span className="stat-value">{allData.length > 0 ? Math.min(...allData.map(d => d.rsi_6)).toFixed(2) : '-'}</span><span className="stat-label">最低RSI(6)</span></div>
        <div className="stat-card warning"><span className="stat-value">{allData.filter(d => d.rsi_6 < 10).length}</span><span className="stat-label">极度超卖</span></div>
        <div className="stat-card"><span className="stat-value">{allData.filter(d => d.rsi_6 >= 10 && d.rsi_6 < 20).length}</span><span className="stat-label">中度超卖</span></div>
      </div>

      {loading ? <div className="loading">加载中...</div> :
       error ? <div className="error-message"><AlertCircle size={48} /><p>{error}</p><button className="btn btn-primary" onClick={fetchOversoldETFs}>重新加载</button></div> :
       allData.length === 0 ? <div className="empty-message"><p>暂无RSI6 &lt; 20的ETF数据</p></div> :
       <>
        <div className="data-table-container">
          <table className="data-table">
            <thead><tr><th>排名</th><th>ETF代码</th><th>ETF名称</th><th>最新价</th><th>涨跌幅</th>
              <th className={`sortable ${sortBy === 'rsi_6' ? 'active' : ''}`} onClick={() => handleSort('rsi_6')}>RSI(6) {sortBy === 'rsi_6' && <ArrowUp size={14} />}</th>
              <th className={`sortable ${sortBy === 'rsi_12' ? 'active' : ''}`} onClick={() => handleSort('rsi_12')}>RSI(12) {sortBy === 'rsi_12' && <ArrowUp size={14} />}</th>
              <th className={`sortable ${sortBy === 'rsi_24' ? 'active' : ''}`} onClick={() => handleSort('rsi_24')}>RSI(24) {sortBy === 'rsi_24' && <ArrowUp size={14} />}</th>
              <th>日期</th></tr></thead>
            <tbody>
              {displayData.map((etf, idx) => {
                const rank = (currentPage - 1) * pageSize + idx + 1;
                return (
                  <tr key={etf.ts_code} className={rank <= 3 ? 'top-rank' : ''}>
                    <td className="rank">{rank <= 3 ? <span className={`rank-badge rank-${rank}`}>{rank}</span> : rank}</td>
                    <td className="code">{etf.ts_code}</td>
                    <td className="name">{etf.name}</td>
                    <td className="price">¥{etf.close?.toFixed(3)}</td>
                    <td className={`change ${etf.pct_chg < 0 ? 'negative' : 'positive'}`}>{etf.pct_chg > 0 ? '+' : ''}{etf.pct_chg}%</td>
                    <td className={`rsi ${getRSIColor(etf.rsi_6)}`}>{etf.rsi_6?.toFixed(2)}</td>
                    <td className={`rsi ${getRSIColor(etf.rsi_12)}`}>{etf.rsi_12?.toFixed(2)}</td>
                    <td className={`rsi ${getRSIColor(etf.rsi_24)}`}>{etf.rsi_24?.toFixed(2)}</td>
                    <td className="date">{etf.trade_date}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        
        <div className="pagination">
          <button disabled={currentPage === 1} onClick={() => setCurrentPage(p => p - 1)}><ChevronLeft size={18} />上一页</button>
          <span className="page-info">第 {currentPage} / {totalPages} 页 (共{allData.length}条)</span>
          <button disabled={currentPage === totalPages} onClick={() => setCurrentPage(p => p + 1)}>下一页<ChevronRight size={18} /></button>
        </div>
       </>}
    </div>
  );
};

const PlaceholderModule: React.FC<{ name: string; desc: string }> = ({ name, desc }) => (
  <div className="placeholder-module">
    <div className="placeholder-icon-large"><Activity size={64} /></div>
    <h3>{name}</h3><p>{desc}><div className="coming-soon">功能开发中...</div>
  </div>
);

const StockAnalysis: React.FC = () => {
  const [activeTab, setActiveTab] = useState('oversold');
  const [searchCode, setSearchCode] = useState('');
  const activeModule = subModules.find(m => m.id === activeTab);

  return (
    <div className="stock-analysis">
      <div className="page-header"><h2>个股分析</h2><p>多维度个股诊断 · 趋势/形态/做T/超跌</p></div>
      <div className="search-bar glass-card">
        <Search size={20} />
        <input type="text" placeholder="输入股票代码或名称..." value={searchCode} onChange={(e) => setSearchCode(e.target.value)} />
        <button className="btn btn-primary">分析</button>
      </div>
      <div className="submodule-tabs">
        {subModules.map((mod) => (
          <button key={mod.id} className={`submodule-tab ${activeTab === mod.id ? 'active' : ''}`} onClick={() => setActiveTab(mod.id)}>
            <mod.icon size={18} />
            <div className="tab-content"><span className="tab-name">{mod.name}</span><span className="tab-desc">{mod.desc}</span></div>
          </button>
        ))}
      </div>
      <div className="analysis-content glass-card">
        {activeTab === 'oversold' ? <OversoldAnalysis /> : <PlaceholderModule name={activeModule?.name || ''} desc={activeModule?.desc || ''} />}
      </div>
    </div>
  );
};

export default StockAnalysis;
