import React, { useEffect, useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { 
  Activity, 
  Target, 
  BarChart3, 
  PieChart,
  Clock,
  Filter,
  AlertCircle,
  Layers,
  Sparkles,
  BookOpen
} from 'lucide-react';
import './SectorRotationV2.css';

// 板块数据类型
interface SectorScore {
  code: string;
  name: string;
  cluster: string;
  clusterId: number;
  totalScore: number;
  trendScore: number;
  volumeScore: number;
  sharpeScore: number;
  breadthScore: number;
  change5d: number;
  change20d: number;
  volatility20d: number;
  amountRatio: number;
  inPool: boolean;
  signal: 'buy' | 'hold' | 'sell' | 'strong_sell';
  rank: number;
}

interface StrategyStatus {
  lastUpdate: string;
  nextRebalance: string;
  poolSize: number;
  holdingCount: number;
  todayReturn: number;
  totalReturn: number;
}

// 模拟数据
const generateMockData = (): SectorScore[] => {
  const clusters = ['科技成长', '消费医药', '金融地产', '周期资源', '高端制造', '新能源'];
  const sectors = [
    { name: '半导体', cluster: '科技成长' },
    { name: '人工智能', cluster: '科技成长' },
    { name: '云计算', cluster: '科技成长' },
    { name: '创新药', cluster: '消费医药' },
    { name: '医疗器械', cluster: '消费医药' },
    { name: '白酒', cluster: '消费医药' },
    { name: '证券', cluster: '金融地产' },
    { name: '银行', cluster: '金融地产' },
    { name: '地产', cluster: '金融地产' },
    { name: '有色金属', cluster: '周期资源' },
    { name: '煤炭', cluster: '周期资源' },
    { name: '化工', cluster: '周期资源' },
    { name: '军工', cluster: '高端制造' },
    { name: '机器人', cluster: '高端制造' },
    { name: '光伏', cluster: '新能源' },
    { name: '锂电池', cluster: '新能源' },
    { name: '储能', cluster: '新能源' },
    { name: '稀土永磁', cluster: '周期资源' },
    { name: 'CPO概念', cluster: '科技成长' },
    { name: '脑机接口', cluster: '科技成长' },
  ];

  return sectors.map((s, i) => {
    const trendScore = Math.random() * 40;
    const volumeScore = Math.random() * 30;
    const sharpeScore = Math.random() * 20;
    const breadthScore = Math.random() * 10;
    const totalScore = trendScore + volumeScore + sharpeScore + breadthScore;
    
    let signal: 'buy' | 'hold' | 'sell' | 'strong_sell' = 'sell';
    if (totalScore >= 90) signal = 'buy';
    else if (totalScore >= 70) signal = 'hold';
    else if (totalScore >= 40) signal = 'sell';
    else signal = 'strong_sell';

    return {
      code: `885${(100 + i).toString().slice(1)}.TI`,
      name: s.name,
      cluster: s.cluster,
      clusterId: clusters.indexOf(s.cluster),
      totalScore: parseFloat(totalScore.toFixed(2)),
      trendScore: parseFloat(trendScore.toFixed(2)),
      volumeScore: parseFloat(volumeScore.toFixed(2)),
      sharpeScore: parseFloat(sharpeScore.toFixed(2)),
      breadthScore: parseFloat(breadthScore.toFixed(2)),
      change5d: parseFloat((Math.random() * 20 - 5).toFixed(2)),
      change20d: parseFloat((Math.random() * 40 - 10).toFixed(2)),
      volatility20d: parseFloat((Math.random() * 30 + 10).toFixed(2)),
      amountRatio: parseFloat((Math.random() * 2 + 0.5).toFixed(2)),
      inPool: totalScore > 50,
      signal,
      rank: 0
    };
  }).sort((a, b) => b.totalScore - a.totalScore)
    .map((s, i) => ({ ...s, rank: i + 1 }));
};

const SectorRotationV2: React.FC = () => {
  const [sectors, setSectors] = useState<SectorScore[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCluster, setSelectedCluster] = useState<string>('all');
  const [selectedSignal, setSelectedSignal] = useState<string>('all');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');

  const strategyStatus: StrategyStatus = {
    lastUpdate: '2025-02-27 15:30:00',
    nextRebalance: '2025-02-28 09:30:00',
    poolSize: 156,
    holdingCount: 5,
    todayReturn: 1.23,
    totalReturn: 14.46
  };

  useEffect(() => {
    setTimeout(() => {
      setSectors(generateMockData());
      setLoading(false);
    }, 600);
  }, []);

  const filteredSectors = useMemo(() => {
    return sectors.filter(s => {
      const clusterMatch = selectedCluster === 'all' || s.cluster === selectedCluster;
      const signalMatch = selectedSignal === 'all' || s.signal === selectedSignal;
      return clusterMatch && signalMatch;
    });
  }, [sectors, selectedCluster, selectedSignal]);

  const buySignals = useMemo(() => 
    sectors.filter(s => s.signal === 'buy').slice(0, 5),
    [sectors]
  );

  const getSignalStyle = (signal: string) => {
    switch (signal) {
      case 'buy': return { bg: '#34C759', text: '#fff', lightBg: 'rgba(52, 199, 89, 0.1)' };
      case 'hold': return { bg: '#007AFF', text: '#fff', lightBg: 'rgba(0, 122, 255, 0.1)' };
      case 'sell': return { bg: '#FF9500', text: '#fff', lightBg: 'rgba(255, 149, 0, 0.1)' };
      case 'strong_sell': return { bg: '#FF3B30', text: '#fff', lightBg: 'rgba(255, 59, 48, 0.1)' };
      default: return { bg: '#8E8E93', text: '#fff', lightBg: 'rgba(142, 142, 147, 0.1)' };
    }
  };

  const getSignalText = (signal: string) => {
    switch (signal) {
      case 'buy': return '买入';
      case 'hold': return '持有';
      case 'sell': return '卖出';
      case 'strong_sell': return '清仓';
      default: return '观望';
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 90) return '#34C759';
    if (score >= 70) return '#007AFF';
    if (score >= 40) return '#FF9500';
    return '#FF3B30';
  };

  if (loading) {
    return (
      <div className="sector-rotation-v2">
        <div className="loading-container">
          <Activity size={32} className="loading-icon" />
          <p>计算板块得分中...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="sector-rotation-v2">
      {/* 页面标题 */}
      <div className="page-header">
        <div className="header-title">
          <Sparkles size={24} className="title-icon" />
          <div>
            <h1>板块轮动 Pro</h1>
            <p>K-Means聚类 + 微观阻力打分系统</p>
          </div>
        </div>
        <Link 
          to="/doc/sector_rotation_algorithm" 
          className="algorithm-link"
        >
          <BookOpen size={18} />
          <span>算法说明</span>
        </Link>
      </div>

      {/* 统计卡片 */}
      <div className="stats-row">
        <div className="stat-card">
          <span className="stat-label">核心观察池</span>
          <span className="stat-value">{strategyStatus.poolSize}</span>
          <span className="stat-unit">个板块</span>
        </div>
        <div className="stat-card highlight">
          <span className="stat-label">当前持仓</span>
          <span className="stat-value">{strategyStatus.holdingCount}</span>
          <span className="stat-unit">个板块</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">策略年化收益</span>
          <span className="stat-value positive">+{strategyStatus.totalReturn}%</span>
          <span className="stat-unit">2016至今</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">今日收益</span>
          <span className="stat-value positive">+{strategyStatus.todayReturn}%</span>
          <span className="stat-unit">实时</span>
        </div>
      </div>

      {/* 买入信号 */}
      {buySignals.length > 0 && (
        <div className="section">
          <div className="section-header">
            <Target size={18} />
            <h2>今日买入信号</h2>
            <span className="badge">{buySignals.length} 个板块</span>
          </div>
          <div className="signals-row">
            {buySignals.map((sector, idx) => (
              <div key={sector.code} className="signal-card">
                <div className="signal-rank">#{idx + 1}</div>
                <div className="signal-main">
                  <span className="signal-name">{sector.name}</span>
                  <span className="signal-cluster">{sector.cluster}</span>
                </div>
                <div className="signal-score">
                  <span className="score-value">{sector.totalScore.toFixed(1)}</span>
                  <span className="score-label">分</span>
                </div>
                <div className="signal-metrics">
                  <span className={sector.change5d >= 0 ? 'up' : 'down'}>
                    {sector.change5d >= 0 ? '+' : ''}{sector.change5d}%
                  </span>
                  <span className="metric-divider">·</span>
                  <span>量能 {sector.amountRatio}x</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 过滤器 */}
      <div className="filters-bar">
        <div className="filter-group">
          <Filter size={14} />
          <select 
            value={selectedCluster} 
            onChange={(e) => setSelectedCluster(e.target.value)}
          >
            <option value="all">全部聚类</option>
            <option value="科技成长">科技成长</option>
            <option value="消费医药">消费医药</option>
            <option value="金融地产">金融地产</option>
            <option value="周期资源">周期资源</option>
            <option value="高端制造">高端制造</option>
            <option value="新能源">新能源</option>
          </select>
        </div>

        <div className="filter-group">
          <select 
            value={selectedSignal} 
            onChange={(e) => setSelectedSignal(e.target.value)}
          >
            <option value="all">全部信号</option>
            <option value="buy">买入 (≥90分)</option>
            <option value="hold">持有 (70-89分)</option>
            <option value="sell">卖出 (40-69分)</option>
            <option value="strong_sell">清仓 (&lt;40分)</option>
          </select>
        </div>

        <div className="view-toggle">
          <button 
            className={viewMode === 'grid' ? 'active' : ''}
            onClick={() => setViewMode('grid')}
          >
            <PieChart size={14} />
            网格
          </button>
          <button 
            className={viewMode === 'list' ? 'active' : ''}
            onClick={() => setViewMode('list')}
          >
            <BarChart3 size={14} />
            列表
          </button>
        </div>

        <div className="update-time">
          <Clock size={14} />
          <span>更新于 {strategyStatus.lastUpdate}</span>
        </div>
      </div>

      {/* 板块列表 */}
      <div className="section">
        <div className="section-header">
          <Layers size={18} />
          <h2>板块评分排行</h2>
          <span className="count">共 {filteredSectors.length} 个</span>
        </div>

        {viewMode === 'grid' ? (
          <div className="sectors-grid">
            {filteredSectors.map((sector) => {
              const signalStyle = getSignalStyle(sector.signal);
              const scoreColor = getScoreColor(sector.totalScore);
              
              return (
                <div key={sector.code} className="sector-card">
                  <div className="card-top">
                    <span className="rank">#{sector.rank}</span>
                    <span 
                      className="signal-tag"
                      style={{ background: signalStyle.bg, color: signalStyle.text }}
                    >
                      {getSignalText(sector.signal)}
                    </span>
                  </div>

                  <div className="card-info">
                    <h3 className="sector-name">{sector.name}</h3>
                    <span className="cluster">{sector.cluster}</span>
                  </div>

                  <div className="score-display">
                    <span className="score-number" style={{ color: scoreColor }}>
                      {sector.totalScore.toFixed(1)}
                    </span>
                    <div className="score-bar-bg">
                      <div 
                        className="score-bar-fill"
                        style={{ 
                          width: `${sector.totalScore}%`,
                          background: scoreColor
                        }}
                      />
                    </div>
                  </div>

                  <div className="factors">
                    <div className="factor">
                      <span className="factor-name">趋势</span>
                      <div className="factor-bar">
                        <div 
                          className="factor-fill"
                          style={{ width: `${(sector.trendScore / 40) * 100}%` }}
                        />
                      </div>
                      <span className="factor-value">{sector.trendScore.toFixed(1)}</span>
                    </div>
                    <div className="factor">
                      <span className="factor-name">资金</span>
                      <div className="factor-bar">
                        <div 
                          className="factor-fill"
                          style={{ width: `${(sector.volumeScore / 30) * 100}%` }}
                        />
                      </div>
                      <span className="factor-value">{sector.volumeScore.toFixed(1)}</span>
                    </div>
                    <div className="factor">
                      <span className="factor-name">夏普</span>
                      <div className="factor-bar">
                        <div 
                          className="factor-fill"
                          style={{ width: `${(sector.sharpeScore / 20) * 100}%` }}
                        />
                      </div>
                      <span className="factor-value">{sector.sharpeScore.toFixed(1)}</span>
                    </div>
                    <div className="factor">
                      <span className="factor-name">广度</span>
                      <div className="factor-bar">
                        <div 
                          className="factor-fill"
                          style={{ width: `${(sector.breadthScore / 10) * 100}%` }}
                        />
                      </div>
                      <span className="factor-value">{sector.breadthScore.toFixed(1)}</span>
                    </div>
                  </div>

                  <div className="card-metrics">
                    <div className="metric">
                      <span className="metric-label">5日</span>
                      <span className={`metric-value ${sector.change5d >= 0 ? 'up' : 'down'}`}>
                        {sector.change5d >= 0 ? '+' : ''}{sector.change5d}%
                      </span>
                    </div>
                    <div className="metric">
                      <span className="metric-label">20日</span>
                      <span className={`metric-value ${sector.change20d >= 0 ? 'up' : 'down'}`}>
                        {sector.change20d >= 0 ? '+' : ''}{sector.change20d}%
                      </span>
                    </div>
                    <div className="metric">
                      <span className="metric-label">量能比</span>
                      <span className="metric-value">{sector.amountRatio}x</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="sectors-table-wrapper">
            <table className="sectors-table">
              <thead>
                <tr>
                  <th>排名</th>
                  <th>板块</th>
                  <th>聚类</th>
                  <th>综合得分</th>
                  <th>趋势</th>
                  <th>资金</th>
                  <th>夏普</th>
                  <th>广度</th>
                  <th>5日涨跌</th>
                  <th>信号</th>
                </tr>
              </thead>
              <tbody>
                {filteredSectors.map((sector) => {
                  const signalStyle = getSignalStyle(sector.signal);
                  const scoreColor = getScoreColor(sector.totalScore);
                  return (
                    <tr key={sector.code}>
                      <td className="rank-cell">#{sector.rank}</td>
                      <td className="name-cell">
                        <span className="name">{sector.name}</span>
                      </td>
                      <td>
                        <span className="cluster-tag">{sector.cluster}</span>
                      </td>
                      <td>
                        <span className="score-cell" style={{ color: scoreColor }}>
                          {sector.totalScore.toFixed(1)}
                        </span>
                      </td>
                      <td>{sector.trendScore.toFixed(1)}</td>
                      <td>{sector.volumeScore.toFixed(1)}</td>
                      <td>{sector.sharpeScore.toFixed(1)}</td>
                      <td>{sector.breadthScore.toFixed(1)}</td>
                      <td className={sector.change5d >= 0 ? 'up' : 'down'}>
                        {sector.change5d >= 0 ? '+' : ''}{sector.change5d}%
                      </td>
                      <td>
                        <span 
                          className="table-signal"
                          style={{ background: signalStyle.bg, color: signalStyle.text }}
                        >
                          {getSignalText(sector.signal)}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 策略说明 */}
      <div className="info-section">
        <div className="info-card">
          <h4>
            <AlertCircle size={16} />
            策略说明
          </h4>
          <p>
            本策略采用<strong>双频共振</strong>架构：月度运行 K-means++ 聚类 + 基本面剔除 + 夏普优选构建核心观察池；
            日频对池内板块进行四维打分（趋势阻力40% + 资金突变30% + 夏普比率20% + 赚钱效应10%），
            采用连续分位数映射生成0-100浮点得分，≥90分买入，同聚类防重配，风险平价仓位管理。
          </p>
        </div>
        <div className="info-card">
          <h4>
            <Clock size={16} />
            调仓规则
          </h4>
          <p>
            <strong>月度调仓</strong>：每月最后一个交易日盘后更新核心观察池<br/>
            <strong>日频调仓</strong>：每日收盘后15:30计算得分，次日09:30执行交易
          </p>
        </div>
      </div>
    </div>
  );
};

export default SectorRotationV2;
