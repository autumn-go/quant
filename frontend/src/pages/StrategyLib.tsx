import React, { useState } from 'react';
import { Plus, Play, Edit2, Trash2, X } from 'lucide-react';
import StrategyEditor from '../components/StrategyEditor';
import './StrategyLib.css';

const strategies = [
  { id: 1, name: '双均线金叉', type: 'technical', status: 'active', return: '+15.3%', code: '' },
  { id: 2, name: 'MACD背离', type: 'technical', status: 'active', return: '+8.7%', code: '' },
  { id: 3, name: 'RSI超买超卖', type: 'technical', status: 'inactive', return: '-2.1%', code: '' },
  { id: 4, name: '动量因子', type: 'factor', status: 'active', return: '+22.5%', code: '' },
];

const StrategyLib: React.FC = () => {
  const [showEditor, setShowEditor] = useState(false);
  const [editingStrategy, setEditingStrategy] = useState<typeof strategies[0] | null>(null);

  const handleNewStrategy = () => {
    setEditingStrategy(null);
    setShowEditor(true);
  };

  const handleEditStrategy = (strategy: typeof strategies[0]) => {
    setEditingStrategy(strategy);
    setShowEditor(true);
  };

  const handleSaveStrategy = (code: string, params: Record<string, any>) => {
    console.log('保存策略:', code, params);
    // TODO: 调用 API 保存
  };

  if (showEditor) {
    return (
      <div className="strategy-lib">
        <div className="editor-header">
          <button className="btn btn-outline" onClick={() => setShowEditor(false)}>
            <X size={16} />
            返回列表
          </button>
          <h3>{editingStrategy ? `编辑: ${editingStrategy.name}` : '新建策略'}</h3>
        </div>
        
        <div className="editor-container">
          <StrategyEditor
            initialCode={editingStrategy?.code}
            onSave={handleSaveStrategy}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="strategy-lib"
    >
      <div className="page-header">
        <h2>策略库</h2>
        <p>策略管理 · 编写/测试/部署</p>
      </div>

      <div className="strategy-actions">
        <button className="btn btn-primary" onClick={handleNewStrategy}>
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
              <button className="action-btn" onClick={() => handleEditStrategy(s)}><Edit2 size={16} /></button>
              <button className="action-btn delete"><Trash2 size={16} /></button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default StrategyLib;
