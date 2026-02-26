import React from 'react';
import { Play } from 'lucide-react';
import './Backtest.css';

const backtests = [
  { id: 1, strategy: '双均线金叉', period: '2024-01-01 ~ 2024-12-31', status: 'completed', return: '+15.3%', sharpe: 1.25 },
  { id: 2, strategy: 'MACD背离', period: '2024-06-01 ~ 2024-12-31', status: 'running', return: '-', sharpe: '-' },
];

const Backtest: React.FC = () => (
  <div className="backtest">
    <div className="page-header">
      <h2>回测中心</h2>
      <p>策略回测验证 · 绩效分析</p>
    </div>

    <div className="backtest-actions">
      <button className="btn btn-primary">
        <Play size={18} />
        新建回测
      </button>
    </div>

    <div className="backtest-list glass-card">
      <div className="list-header">
        <span>策略</span>
        <span>回测区间</span>
        <span>状态</span>
        <span>收益率</span>
        <span>夏普比率</span>
      </div>

      {backtests.map((b) => (
        <div key={b.id} className="list-item">
          <span className="backtest-strategy">{b.strategy}</span>
          <span className="backtest-period">{b.period}</span>          
          <span className={`status-badge ${b.status}`}>
            {b.status === 'completed' ? '已完成' : '运行中'}
          </span>
          
          <span className={`backtest-return ${b.return.startsWith('+') ? 'up' : 'down'}`}>
            {b.return}
          </span>          
          <span className="backtest-sharpe">{b.sharpe}</span>
        </div>
      ))}
    </div>
  </div>
);

export default Backtest;
