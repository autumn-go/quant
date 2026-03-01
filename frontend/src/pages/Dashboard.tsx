// 总览仪表盘 - 新版设计
import React, { useEffect, useState } from 'react';
import { 
  Activity, 
  BarChart3, 
  Zap, 
  Target,
  Flame,
  PieChart,
  ArrowUpRight,
  ArrowDownRight
} from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { marketAPI, strategyAPI } from '../api';
import './Dashboard.css';

interface MarketIndex {
  name: string;
  code: string;
  value: number;
  change: number;
  trend: string;
  signal: string;
}

interface LimitUpStock {
  rank: number;
  name: string;
  code: string;
  limitUpDays: number;
  concept: string;
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
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, []);

  // 模拟涨停梯队数据
  const limitUpStocks: LimitUpStock[] = [
    { rank: 1, name: '东方精工', code: '002611.SZ', limitUpDays: 5, concept: '机器人' },
    { rank: 2, name: '四川金顶', code: '600678.SH', limitUpDays: 4, concept: '氢能源' },
    { rank: 3, name: '康普顿', code: '603798.SH', limitUpDays: 3, concept: '氢能源' },
    { rank: 4, name: '达意隆', code: '002209.SZ', limitUpDays: 3, concept: '机器人' },
    { rank: 5, name: '神驰机电', code: '603109.SH', limitUpDays: 2, concept: '新能源汽车' },
  ];

  // 模拟市场风格数据
  const marketStyle = {
    largeCap: { value: 45, trend: 'up' },
    smallCap: { value: 55, trend: 'down' },
    growth: { value: 60, trend: 'up' },
    value: { value: 40, trend: 'down' },
  };

  // 模拟图表数据
  const chartData = [
    { time: '09:30', value: 4140, volume: 1200 },
    { time: '10:30', value: 4150, volume: 1500 },
    { time: '11:30', value: 4145, volume: 1100 },
    { time: '13:00', value: 4148, volume: 1300 },
    { time: '14:00', value: 4142, volume: 1400 },
    { time: '15:00', value: 4146, volume: 1600 },
  ];

  if (loading) {
    return <div className="loading-container"><div className="loading" /></div>;
  }

  return (
    <div className="dashboard">
      {/* 页面标题 */}
      <div className="dashboard-header">
        <h1>市场总览</h1>
        <p>{new Date().toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' })}</p>
      </div>

      {/* 第一行：大盘择时 + 市场风格 */}
      <div className="dashboard-row">
        {/* 大盘择时判断 */}
        <div className="dashboard-card market-timing">
          <div className="card-header">
            <Activity size={18} />
            <span>大盘择时判断</span>
          </div>
          
          <div className="timing-chart">
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={chartData}>
                <defs>
                  <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#000000" stopOpacity={0.1}/>
                    <stop offset="95%" stopColor="#000000" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.05)" />
                <XAxis dataKey="time" stroke="#94a3b8" fontSize={11} tickLine={false} />
                <YAxis domain={['dataMin - 10', 'dataMax + 10']} stroke="#94a3b8" fontSize={11} tickLine={false} />
                <Tooltip contentStyle={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '6px', fontSize: '12px' }} />
                <Area type="monotone" dataKey="value" stroke="#000000" strokeWidth={1.5} fillOpacity={1} fill="url(#colorValue)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          <div className="timing-indices">
            {marketData.slice(0, 4).map((item) => (
              <div key={item.code} className="timing-item">
                <div className="timing-name">{item.name}</div>
                <div className="timing-value">{item.value.toLocaleString()}</div>
                <div className={`timing-change ${item.change >= 0 ? 'up' : 'down'}`}>
                  {item.change >= 0 ? '+' : ''}{item.change}%
                </div>
                <div className={`timing-signal ${item.signal === '看多' ? 'bull' : item.signal === '看空' ? 'bear' : 'neutral'}`}>
                  {item.signal}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* 当前市场风格 */}
        <div className="dashboard-card market-style">
          <div className="card-header">
            <PieChart size={18} />
            <span>当前市场风格</span>
          </div>
          
          <div className="style-grid">
            <div className="style-item">
              <div className="style-label">大盘风格</div>
              <div className="style-bar-container">
                <div className="style-bar-bg">
                  <div className="style-bar" style={{ width: `${marketStyle.largeCap.value}%` }} />
                </div>
                <span className="style-percent">{marketStyle.largeCap.value}%</span>
              </div>
              <div className={`style-trend ${marketStyle.largeCap.trend}`}>
                {marketStyle.largeCap.trend === 'up' ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
              </div>
            </div>

            <div className="style-item">
              <div className="style-label">小盘风格</div>
              <div className="style-bar-container">
                <div className="style-bar-bg">
                  <div className="style-bar" style={{ width: `${marketStyle.smallCap.value}%` }} />
                </div>
                <span className="style-percent">{marketStyle.smallCap.value}%</span>
              </div>
              <div className={`style-trend ${marketStyle.smallCap.trend}`}>
                {marketStyle.smallCap.trend === 'up' ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
              </div>
            </div>

            <div className="style-item">
              <div className="style-label">成长风格</div>
              <div className="style-bar-container">
                <div className="style-bar-bg">
                  <div className="style-bar" style={{ width: `${marketStyle.growth.value}%` }} />
                </div>
                <span className="style-percent">{marketStyle.growth.value}%</span>
              </div>
              <div className={`style-trend ${marketStyle.growth.trend}`}>
                {marketStyle.growth.trend === 'up' ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
              </div>
            </div>

            <div className="style-item">
              <div className="style-label">价值风格</div>
              <div className="style-bar-container">
                <div className="style-bar-bg">
                  <div className="style-bar" style={{ width: `${marketStyle.value.value}%` }} />
                </div>
                <span className="style-percent">{marketStyle.value.value}%</span>
              </div>
              <div className={`style-trend ${marketStyle.value.trend}`}>
                {marketStyle.value.trend === 'up' ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 第二行：涨停梯队 */}
      <div className="dashboard-card limit-up">
        <div className="card-header">
          <Flame size={18} />
          <span>涨停梯队</span>
        </div>
        
        <div className="limit-up-table">
          <div className="table-header">
            <span>排名</span>
            <span>股票名称</span>
            <span>代码</span>
            <span>连板天数</span>
            <span>概念板块</span>
          </div>
          {limitUpStocks.map((stock) => (
            <div key={stock.code} className="table-row">
              <span className="rank">{stock.rank}</span>
              <span className="stock-name">{stock.name}</span>
              <span className="stock-code">{stock.code}</span>
              <span className="limit-up-days">
                <Flame size={14} className="flame-icon" />
                {stock.limitUpDays}天
              </span>
              <span className="concept">{stock.concept}</span>
            </div>
          ))}
        </div>
      </div>

      {/* 第三行：策略统计 + 最新信号 */}
      <div className="dashboard-row">
        {/* 策略统计 */}
        <div className="dashboard-card strategy-stats">
          <div className="card-header">
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
                <div className="stat-bar-bg">
                  <div className="stat-bar" style={{ width: `${(stat.active / stat.count) * 100}%` }} />
                </div>
                <span className="stat-return">{stat.return}</span>
              </div>
            ))}
          </div>
        </div>

        {/* 最新信号 */}
        <div className="dashboard-card recent-signals">
          <div className="card-header">
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