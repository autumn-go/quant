// 指数大师 - 指数择时
import React from 'react';
import { Activity, Calendar } from 'lucide-react';
import './IndexMaster.css';

const indexList = [
  { name: '上证指数', code: '000001.SH', value: 4146.63, change: -0.01, trend: 'neutral', signal: '观望' },
  { name: '深证成指', code: '399001.SZ', value: 14503.79, change: 0.19, trend: 'up', signal: '看多' },
  { name: '创业板指', code: '399006.SZ', value: 2928.84, change: 0.63, trend: 'up', signal: '看多' },
  { name: '沪深300', code: '000300.SH', value: 3845.62, change: -0.15, trend: 'down', signal: '看空' },
  { name: '中证500', code: '000905.SH', value: 5623.45, change: 0.32, trend: 'up', signal: '看多' },
  { name: '恒生指数', code: 'HSI', value: 26381.02, change: -1.44, trend: 'down', signal: '看空' },
  { name: '恒生科技', code: 'HSTECH', value: 5109.33, change: -2.87, trend: 'down', signal: '强烈看空' },
  { name: '纳斯达克', code: 'IXIC', value: 18285.16, change: 0.85, trend: 'up', signal: '看多' },
];

const timingSignals = [
  { date: '2026-02-26', index: '上证指数', signal: '观望', reason: 'MACD金叉确认中', confidence: 65 },
  { date: '2026-02-25', index: '创业板指', signal: '看多', reason: '突破20日均线', confidence: 78 },
  { date: '2026-02-24', index: '恒生科技', signal: '看空', reason: '跌破支撑位', confidence: 82 },
  { date: '2026-02-23', index: '沪深300', signal: '观望', reason: '量能不足', confidence: 60 },
];

const IndexMaster: React.FC = () => {
  return (
    <div className="index-master">
      <div className="page-header">
        <h2>指数大师</h2>
        <p>多维度指数择时分析 · 技术面+资金面+情绪面</p>
      </div>

      {/* 指数卡片网格 */}
      <div className="index-grid">
        {indexList.map((index) => (
          <div key={index.code} className="index-card glass-card">
            <div className="index-card-header">
              <div>
                <div className="index-name">{index.name}</div>
                <div className="index-code">{index.code}</div>
              </div>
              <div className={`signal-tag ${index.signal === '看多' ? 'bull' : index.signal === '看空' ? 'bear' : 'neutral'}`}>
                {index.signal}
              </div>
            </div>
            
            <div className="index-value-section">
              <div className="index-current">{index.value.toLocaleString()}</div>              <div className={`index-change ${index.change >= 0 ? 'up' : 'down'}`}>
                {index.change >= 0 ? '+' : ''}{index.change}%
              </div>
            </div>

            <div className="index-mini-chart">
              {/* 迷你走势图占位 */}
              <div className="mini-chart-placeholder">
                <Activity size={16} />
                <span>走势图</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* 择时信号历史 */}
      <div className="timing-section glass-card">
        <div className="section-title">
          <Calendar size={18} />
          <span>近期择时信号</span>
        </div>
        
        <div className="signal-table">
          <div className="table-header">
            <span>日期</span>
            <span>指数</span>
            <span>信号</span>
            <span>理由</span>
            <span>置信度</span>
          </div>          
          {timingSignals.map((item, idx) => (
            <div key={idx} className="table-row">
              <span>{item.date}</span>
              <span>{item.index}</span>
              <span className={`tag ${item.signal === '看多' ? 'bull' : item.signal === '看空' ? 'bear' : 'neutral'}`}>
                {item.signal}
              </span>
              <span>{item.reason}</span>
              <span className="confidence">{item.confidence}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default IndexMaster;
