// 总览仪表盘
import React from 'react';
import { TrendingUp, TrendingDown, Activity, BarChart3, Zap, Target } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import './Dashboard.css';

// 模拟数据
const marketData = [
  { name: '上证指数', value: 4146.63, change: -0.01, trend: 'down' },
  { name: '深证成指', value: 14503.79, change: 0.19, trend: 'up' },
  { name: '创业板指', value: 2928.84, change: 0.63, trend: 'up' },
  { name: '恒生指数', value: 26381.02, change: -1.44, trend: 'down' },
  { name: '恒生科技', value: 5109.33, change: -2.87, trend: 'down' },
];

const chartData = [
  { time: '09:30', value: 4140 },
  { time: '10:30', value: 4150 },
  { time: '11:30', value: 4145 },
  { time: '13:00', value: 4148 },
  { time: '14:00', value: 4142 },
  { time: '15:00', value: 4146 },
];

const strategyStats = [
  { name: '指数择时', count: 12, active: 8, return: '+15.3%' },
  { name: '风格轮动', count: 8, active: 5, return: '+8.7%' },
  { name: '板块轮动', count: 15, active: 10, return: '+22.1%' },
  { name: '个股策略', count: 25, active: 18, return: '+12.5%' },
];

const recentSignals = [
  { time: '14:32', type: '买入', symbol: '000001.SZ', name: '平安银行', strategy: '趋势跟踪', confidence: 85 },
  { time: '14:28', type: '卖出', symbol: '600000.SH', name: '浦发银行', strategy: '顶底判断', confidence: 78 },
  { time: '14:15', type: '买入', symbol: '000858.SZ', name: '五粮液', strategy: '超跌反弹', confidence: 82 },
  { time: '14:05', type: '观望', symbol: '002415.SZ', name: '海康威视', strategy: '形态识别', confidence: 65 },
];

const Dashboard: React.FC = () => {
  return (
    <div className="dashboard">
      {/* 欢迎区域 */}
      <div className="welcome-section animate-fade-in">
        <h1>欢迎回来，<span className="gradient-text">QuantPro</span></h1>
        <p>今日市场概览 · 2026年2月26日 星期四</p>
      </div>

      {/* 市场指数卡片 */}
      <div className="market-grid">
        {marketData.map((item) => (
          <div 
            key={item.name}
            className="market-card glass-card animate-fade-in"
            style={{ animationDelay: `${index * 0.1}s` }}
          >
            <div className="market-header">
              <span className="market-name">{item.name}</span>
              {item.trend === 'up' ? (
                <TrendingUp className="trend-icon up" size={18} />
              ) : (
                <TrendingDown className="trend-icon down" size={18} />
              )}
            </div>
            <div className="market-value">{item.value.toLocaleString()}</div>
            <div className={`market-change ${item.trend}`}>
              {item.change > 0 ? '+' : ''}{item.change}%
            </div>
          </div>
        ))}
      </div>

      {/* 主图表区域 */}
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
                <XAxis 
                  dataKey="time" 
                  stroke="#64748b"
                  fontSize={12}
                  tickLine={false}
                />
                <YAxis 
                  domain={['dataMin - 10', 'dataMax + 10']}
                  stroke="#64748b"
                  fontSize={12}
                  tickLine={false}
                  tickFormatter={(value) => value.toFixed(0)}
                />
                <Tooltip 
                  contentStyle={{
                    background: '#111827',
                    border: '1px solid rgba(0,212,255,0.3)',
                    borderRadius: '8px',
                    color: '#fff'
                  }}
                />
                
                <Area 
                  type="monotone" 
                  dataKey="value" 
                  stroke="#00d4ff" 
                  strokeWidth={2}
                  fillOpacity={1} 
                  fill="url(#colorValue)" 
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* 策略统计 + 最新信号 */}
      <div className="bottom-grid">
        {/* 策略统计 */}
        <div className="strategy-stats glass-card animate-fade-in delay-300">
          <div className="section-header">
            <BarChart3 size={18} />
            <span>策略统计</span>
          </div>
          
          <div className="stats-list">
            {strategyStats.map((stat, index) => (
              <div key={stat.name} className="stat-item">
                <div className="stat-info">
                  <span className="stat-name">{stat.name}</span>
                  <span className="stat-count">{stat.active}/{stat.count} 运行中</span>
                </div>                <div className="stat-bar">
                  <div 
                    className="stat-progress"
                    style={{ width: `${(stat.active / stat.count) * 100}%` }}
                  />
                </div>
                
                <span className="stat-return">{stat.return}</span>
              </div>
            ))}
          </div>
        </div>

        {/* 最新信号 */}
        <div className="recent-signals glass-card animate-fade-in delay-400">
          <div className="section-header"
          >
            <Zap size={18} />
            <span>最新信号</span>
          </div>
          
          <div className="signals-list">
            {recentSignals.map((signal, index) => (
              <div key={index} className="signal-item">
                <div className="signal-main">
                  <div className={`signal-badge ${signal.type}`}>
                    {signal.type}
                  </div>
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
