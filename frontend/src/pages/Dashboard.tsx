// 更新后的 Dashboard - 使用真实 API
import React, { useEffect, useState } from 'react';
import { TrendingUp, TrendingDown, Activity, BarChart3, Zap, Target } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { marketAPI, strategyAPI } from '../../api';
import './Dashboard.css';

interface MarketIndex {
  name: string;
  code: string;
  value: number;
  change: number;
  trend: string;
}

interface StrategyStat {
  name: string;
  count: number;
  active: number;
  return: string;
}

interface Signal {
  time: string;
  type: string;
  symbol: string;
  name: string;
  strategy: string;
  confidence: number;
}

const Dashboard: React.FC = () => {
  const [marketData, setMarketData] = useState<MarketIndex[]>([]);
  const [strategyStats, setStrategyStats] = useState<StrategyStat[]>([]);
  const [recentSignals, setRecentSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [indices, stats, signals] = await Promise.all([
          marketAPI.getIndices(),
          strategyAPI.getStats(),
          strategyAPI.getRecentSignals(),
        ]);
        
        setMarketData(indices);
        setStrategyStats(stats);
        setRecentSignals(signals);
      } catch (error) {
        console.error('Failed to fetch data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    // 每 30 秒刷新一次
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, []);

  // 模拟图表数据（后续用真实数据）
  const chartData = [
    { time: '09:30', value: 4140 },
    { time: '10:30', value: 4150 },
    { time: '11:30', value: 4145 },
    { time: '13:00', value: 4148 },
    { time: '14:00', value: 4142 },
    { time: '15:00', value: 4146 },
  ];

  if (loading) {
    return <div className="loading-container"><div className="loading" /></div>;
  }

  return (
    <div className="dashboard">
      <div className="welcome-section animate-fade-in">
        <h1>欢迎回来，<span className="gradient-text">QuantPro</span></h1>
        <p>今日市场概览 · {new Date().toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' })}</p>
      </div>

      <div className="market-grid">
        {marketData.map((item, idx) => (
          <div 
            key={item.code}
            className="market-card glass-card animate-fade-in"
            style={{ animationDelay: `${idx * 0.1}s` }}
          >
            <div className="market-header">
              <span className="market-name">{item.name}</span>
              {item.change >= 0 ? (
                <TrendingUp className="trend-icon up" size={18} />
              ) : (
                <TrendingDown className="trend-icon down" size={18} />
              )}
            </div>
            <div className="market-value">{item.value.toLocaleString()}</div>
            <div className={`market-change ${item.change >= 0 ? 'up' : 'down'}`}>
              {item.change >= 0 ? '+' : ''}{item.change}%
            </div>
          </div>
        ))}
      </div>

      <div className="chart-section animate-fade-in delay-200">
        <div className="chart-card glass-card">
          <div className="chart-header">
            <div className="chart-title">
              <Activity size={18} />
              <span>上证指数分时走势</span>
            </div>
            <div className="chart-tabs">
              <button className="tab active">分时</button>
              <button className="tab">日K</button>
              <button className="tab">周K</button>
            </div>
          </div>
          
          <div className="chart-container">
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={chartData}>
                <defs>
                  <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#00d4ff" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#00d4ff" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,212,255,0.1)" />
                <XAxis dataKey="time" stroke="#64748b" fontSize={12} tickLine={false} />
                <YAxis domain={['dataMin - 10', 'dataMax + 10']} stroke="#64748b" fontSize={12} tickLine={false} />
                <Tooltip contentStyle={{ background: '#111827', border: '1px solid rgba(0,212,255,0.3)', borderRadius: '8px', color: '#fff' }} />
                <Area type="monotone" dataKey="value" stroke="#00d4ff" strokeWidth={2} fillOpacity={1} fill="url(#colorValue)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="bottom-grid">
        <div className="strategy-stats glass-card animate-fade-in delay-300">
          <div className="section-header">
            <BarChart3 size={18} />
            <span>策略统计</span>
          </div>
          
          <div className="stats-list">
            {strategyStats.map((stat) => (
              <div key={stat.name} className="stat-item">
                <div className="stat-info">
                  <span className="stat-name">{stat.name}</span>
                  <span className="stat-count">{stat.active}/{stat.count} 运行中</span>
                </div>
                <div className="stat-bar">
                  <div className="stat-progress" style={{ width: `${(stat.active / stat.count) * 100}%` }} />
                </div>
                <span className="stat-return">{stat.return}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="recent-signals glass-card animate-fade-in delay-400">
          <div className="section-header">
            <Zap size={18} />
            <span>最新信号</span>
          </div>
          
          <div className="signals-list">
            {recentSignals.map((signal, idx) => (
              <div key={idx} className="signal-item">
                <div className="signal-main">
                  <div className={`signal-badge ${signal.type}`}>{signal.type}</div>
                  <div className="signal-info">
                    <span className="signal-symbol">{signal.symbol}</span>
                    <span className="signal-name">{signal.name}</span>
                  </div>
                </div>
                
                <div className="signal-meta">
                  <span className="signal-strategy">{signal.strategy}</span>
                  <div className="signal-confidence">
                    <Target size={12} />
                    <span>{signal.confidence}%</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;