import React from 'react';
import { PieChart, TrendingUp, Shield, Target } from 'lucide-react';
import './StyleMaster.css';

const styleData = [
  { name: '大盘价值', weight: 35, trend: 'up', desc: '低估值+高股息' },
  { name: '大盘成长', weight: 25, trend: 'down', desc: '科技龙头' },
  { name: '中小盘价值', weight: 20, trend: 'up', desc: '周期复苏' },
  { name: '中小盘成长', weight: 20, trend: 'neutral', desc: '专精特新' },
];

const StyleMaster: React.FC = () => (
  <div className="style-master">
    <div className="page-header">
      <h2>宽基大师</h2>
      <p>风格轮动配置 · 价值/成长/大盘/小盘四象限</p>
    </div>

    <div className="style-grid">
      {styleData.map((style) => (
        <div key={style.name} className="style-card glass-card">
          <div className="style-header">
            <div className="style-icon">
              {style.trend === 'up' ? <TrendingUp size={20} /> : <Shield size={20} />}
            </div>
            <div className="style-info">
              <div className="style-name">{style.name}</div>
              <div className="style-desc">{style.desc}</div>
            </div>
          </div>
          
          <div className="style-weight">
            <div className="weight-bar">
              <div 
                className="weight-fill"
                style={{ width: `${style.weight}%` }}
              />
            </div>
            <span className="weight-value">{style.weight}%</span>
          </div>
        </div>
      ))}
    </div>
  </div>
);

export default StyleMaster;
