import React from 'react';
import { RotateCcw, Flame, TrendingUp, Zap } from 'lucide-react';
import './SectorRotation.css';

const sectors = [
  { name: '人工智能', change: 5.23, heat: 95, trend: 'up' },
  { name: '半导体', change: 3.87, heat: 88, trend: 'up' },
  { name: '新能源', change: 2.15, heat: 76, trend: 'up' },
  { name: '医药生物', change: -1.23, heat: 45, trend: 'down' },
  { name: '银行', change: 0.56, heat: 62, trend: 'neutral' },
  { name: '房地产', change: -2.34, heat: 32, trend: 'down' },
  { name: '有色金属', change: 4.12, heat: 82, trend: 'up' },
  { name: '食品饮料', change: -0.78, heat: 55, trend: 'neutral' },
];

const SectorRotation: React.FC = () => (
  <div className="sector-rotation">
    <div className="page-header">
      <h2>板块轮动</h2>
      <p>日频板块轮动监控 · 热点追踪</p>
    </div>

    <div className="sector-grid">
      {sectors.map((sector) => (
        <div key={sector.name} className="sector-card glass-card">
          <div className="sector-header">
            <span className="sector-name">{sector.name}</span>
            <div className={`sector-trend ${sector.trend}`}>
              {sector.trend === 'up' ? <TrendingUp size={16} /> : <Zap size={16} />}
            </div>
          </div>
          
          <div className="sector-change">
            <span className={sector.change >= 0 ? 'up' : 'down'}>
              {sector.change >= 0 ? '+' : ''}{sector.change}%
            </span>
          </div>
          
          <div className="sector-heat">
            <div className="heat-label">
              <Flame size={14} />
              <span>热度 {sector.heat}</span>
            </div>            
            <div className="heat-bar">
              <div 
                className="heat-fill"
                style={{ 
                  width: `${sector.heat}%`,
                  background: sector.heat > 80 
                    ? 'linear-gradient(90deg, #ff4757, #ff6348)' 
                    : sector.heat > 60 
                      ? 'linear-gradient(90deg, #ffaa00, #ffc107)' 
                      : 'linear-gradient(90deg, #00d4ff, #7b68ee)'
                }}
              />
            </div>
          </div>
        </div>
      ))}
    </div>
  </div>
);

export default SectorRotation;
