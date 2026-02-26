import React from 'react';
import { Plus, Play, Edit2, Trash2 } from 'lucide-react';
import './StrategyLib.css';

const strategies = [
  { id: 1, name: '双均线金叉', type: 'technical', status: 'active', return: '+15.3%' },
  { id: 2, name: 'MACD背离', type: 'technical', status: 'active', return: '+8.7%' },
  { id: 3, name: 'RSI超买超卖', type: 'technical', status: 'inactive', return: '-2.1%' },
  { id: 4, name: '动量因子', type: 'factor', status: 'active', return: '+22.5%' },
];

const StrategyLib: React.FC = () => (
  <div className="strategy-lib">
    <div className="page-header">
      <h2>策略库</h2>
      <p>策略管理 · 编写/测试/部署</p>
    </div>

    <div className="strategy-actions">
      <button className="btn btn-primary">
        <Plus size={18} />
        新建策略
      </button>
    </div>

    <div className="strategy-list glass-card">
      <div className="list-header">
        <span>策略名称</span>
        <span>类型</span>
        <span>状态</span>
        <span>累计收益</span>
        <span>操作</span>
      </div>

      {strategies.map((s) => (
        <div key={s.id} className="list-item">
          <span className="strategy-name">{s.name}</span>
          <span className="strategy-type">{s.type}</span>
          <span className={`status-badge ${s.status}`}>{s.status}</span>
          <span className={`strategy-return ${s.return.startsWith('+') ? 'up' : 'down'}`}>
            {s.return}
          </span>          
          <div className="strategy-actions-row">
            <button className="action-btn"><Play size={16} /></button>
            <button className="action-btn"><Edit2 size={16} /></button>
            <button className="action-btn delete"><Trash2 size={16} /></button>
          </div>
        </div>
      ))}
    </div>
  </div>
);

export default StrategyLib;
