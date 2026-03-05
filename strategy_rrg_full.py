#!/usr/bin/env python3
"""
RRG相对轮动图策略 - 增强版
支持历史轨迹计算和全量行业输出
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import json
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 策略参数
PARAMS = {
    'rs_ratio_period': 15,        # RS-Ratio计算周期（15日≈3周）
    'rs_momentum_period': 5,      # RS-Momentum计算周期（5日≈1周）
    'benchmark': '000300.SH',     # 基准指数（沪深300）
}


@dataclass
class RRGSignal:
    """RRG信号"""
    industry_code: str
    industry_name: str
    date: str
    rs_ratio: float
    rs_momentum: float
    quadrant: str


class RRGStrategy:
    """RRG相对轮动图策略"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            # 默认使用data-collector下的数据库
            db_path = str(Path(__file__).parent / 'data-collector' / 'quant_data.db')
        self.db_path = db_path
        self.params = PARAMS
    
    def get_industries(self) -> List[Tuple[str, str]]:
        """获取行业列表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute('SELECT ts_code, name FROM ths_industries ORDER BY ts_code')
        industries = cursor.fetchall()
        conn.close()
        return industries
    
    def get_industry_data(self, industry_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取行业指数数据"""
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql('''
            SELECT * FROM ths_industry_daily 
            WHERE ts_code = ? AND trade_date >= ? AND trade_date <= ?
            ORDER BY trade_date
        ''', conn, params=(industry_code, start_date, end_date))
        conn.close()
        return df
    
    def get_benchmark_data(self, start_date: str, end_date: str) -> pd.DataFrame:
        """获取基准指数数据"""
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql('''
            SELECT * FROM daily_prices 
            WHERE symbol = ? AND date >= ? AND date <= ?
            ORDER BY date
        ''', conn, params=(self.params['benchmark'], start_date, end_date))
        conn.close()
        return df
    
    def calculate_rrg_series(self, industry_code: str, start_date: str, end_date: str) -> List[Dict]:
        """
        计算RRG时间序列（用于绘制轨迹）
        返回每个交易日的RS-Ratio和RS-Momentum
        """
        industry_name = ''
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute('SELECT name FROM ths_industries WHERE ts_code = ?', (industry_code,))
        row = cursor.fetchone()
        if row:
            industry_name = row[0]
        conn.close()
        
        # 获取数据（需要往前推一段时间用于计算EMA）
        pre_start = (datetime.strptime(start_date, '%Y%m%d') - timedelta(days=60)).strftime('%Y%m%d')
        
        industry_df = self.get_industry_data(industry_code, pre_start, end_date)
        benchmark_df = self.get_benchmark_data(pre_start, end_date)
        
        if industry_df.empty or benchmark_df.empty:
            return []
        
        # 对齐日期
        industry_df = industry_df.rename(columns={'trade_date': 'date'})
        benchmark_df = benchmark_df.rename(columns={'date': 'trade_date'})
        
        industry_df['date'] = industry_df['date'].astype(str)
        benchmark_df['trade_date'] = benchmark_df['trade_date'].astype(str)
        
        merged = pd.merge(
            industry_df[['date', 'close']],
            benchmark_df[['trade_date', 'close']],
            left_on='date',
            right_on='trade_date',
            suffixes=('_ind', '_bench')
        )
        
        if merged.empty:
            return []
        
        # 计算相对强度
        merged['rs'] = merged['close_ind'] / merged['close_bench']
        
        # RS-Ratio: RS的EMA平滑，标准化到100
        merged['rs_ratio_raw'] = merged['rs'].ewm(span=self.params['rs_ratio_period']).mean()
        # 使用第rs_ratio_period日作为基准100
        base_idx = min(self.params['rs_ratio_period'], len(merged)-1)
        base_ratio = merged['rs_ratio_raw'].iloc[base_idx]
        merged['rs_ratio'] = merged['rs_ratio_raw'] / base_ratio * 100
        
        # RS-Momentum: RS-Ratio的N日动量，同样标准化到100
        # 计算当前RS-Ratio与N日前的比率，乘以100
        rs_shifted = merged['rs_ratio'].shift(self.params['rs_momentum_period'])
        merged['rs_momentum'] = merged['rs_ratio'] / rs_shifted * 100
        
        # 只返回start_date之后的数据
        merged = merged[merged['date'] >= start_date]
        
        results = []
        for _, row in merged.iterrows():
            if pd.notna(row['rs_ratio']) and pd.notna(row['rs_momentum']):
                quadrant = self._get_quadrant(row['rs_ratio'], row['rs_momentum'])
                results.append({
                    'date': row['date'],
                    'industry_code': industry_code,
                    'industry_name': industry_name,
                    'rs_ratio': round(row['rs_ratio'], 2),
                    'rs_momentum': round(row['rs_momentum'], 2),
                    'quadrant': quadrant
                })
        
        return results
    
    def _get_quadrant(self, rs_ratio: float, rs_momentum: float) -> str:
        """判断RRG象限（Y轴中心为100）"""
        if rs_ratio > 100 and rs_momentum > 100:
            return 'leading'
        elif rs_ratio < 100 and rs_momentum > 100:
            return 'improving'
        elif rs_ratio < 100 and rs_momentum < 100:
            return 'lagging'
        else:
            return 'weakening'
    
    def run(self, start_date: str, end_date: str) -> Dict:
        """
        运行策略，生成完整结果
        包括：
        1. 全量90个行业的最新排名
        2. 每个行业的历史轨迹数据
        """
        logger.info(f"=== RRG策略运行 ({start_date} ~ {end_date}) ===")
        
        industries = self.get_industries()
        logger.info(f"共 {len(industries)} 个行业")
        
        all_signals = []
        all_trails = {}  # 存储每个行业的轨迹
        
        for i, (code, name) in enumerate(industries, 1):
            logger.info(f"[{i}/{len(industries)}] 计算 {name}...")
            
            # 计算完整轨迹
            trail = self.calculate_rrg_series(code, start_date, end_date)
            
            if trail:
                all_trails[code] = {
                    'name': name,
                    'code': code,
                    'trail': trail
                }
                
                # 最新数据用于排名
                latest = trail[-1]
                all_signals.append(latest)
        
        # 按RS-Ratio排序（全量排名）
        all_signals.sort(key=lambda x: x['rs_ratio'], reverse=True)
        
        # 象限统计
        quadrant_stats = {
            'leading': len([s for s in all_signals if s['quadrant'] == 'leading']),
            'improving': len([s for s in all_signals if s['quadrant'] == 'improving']),
            'weakening': len([s for s in all_signals if s['quadrant'] == 'weakening']),
            'lagging': len([s for s in all_signals if s['quadrant'] == 'lagging']),
        }
        
        # 添加排名
        for i, signal in enumerate(all_signals, 1):
            signal['rank'] = i
        
        return {
            'date': end_date,
            'start_date': start_date,
            'benchmark': self.params['benchmark'],
            'params': self.params,
            'quadrant_stats': quadrant_stats,
            'all_industries': all_signals,  # 全量90个行业
            'trails': all_trails  # 每个行业的轨迹数据
        }


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='RRG策略 - 增强版')
    parser.add_argument('--start', type=str, default='20260101',
                       help='开始日期 (YYYYMMDD)')
    parser.add_argument('--end', type=str, default='20260304',
                       help='结束日期 (YYYYMMDD)')
    parser.add_argument('--db', type=str, default=None,
                       help='数据库路径')
    parser.add_argument('--output', type=str, default='rrg_full_result.json',
                       help='输出JSON文件')
    
    args = parser.parse_args()
    
    # 运行策略
    strategy = RRGStrategy(db_path=args.db)
    result = strategy.run(args.start, args.end)
    
    # 保存结果
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    logger.info(f"结果已保存到: {args.output}")
    logger.info(f"共 {len(result['all_industries'])} 个行业")
    logger.info(f"象限分布: {result['quadrant_stats']}")


if __name__ == '__main__':
    main()
