import React, { useEffect, useState } from 'react';
import { Flame, TrendingUp, Zap } from 'lucide-react';
import { marketAPI } from '../api';
import './SectorRotation.css';

interface Sector {
  name: string;
  change: number;
  heat: number;
  trend: string;
}

const SectorRotation: React.FC = () => {
  const [sectors, setSectors] = useState<Sector[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const data = await marketAPI.getSectors();
        setSectors(data);
      } catch (error) {
        console.error('Failed to fetch sectors:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) {
    return <div className="loading-container"><div className="loading" /></div>;
  }

  return (
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
};

export default SectorRotation;