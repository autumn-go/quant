#!/usr/bin/env python3
"""
扩散动量因子策略 - 独立版本
基于国海证券研报《扩散动量因子的应用及探讨》
参数：30日趋势判定（研报原为252日）
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import json
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 策略参数
PARAMS = {
    'trend_period': 30,           # 趋势判定周期（30日）
    'trend_threshold': 0.03,      # 趋势判定阈值（3%）
    'top_n': 6,                   # 选择前N个行业
    'volatility_period': 20,      # 波动率计算周期
}


@dataclass
class DiffusionSignal:
    """扩散动量信号"""
    industry_code: str
    industry_name: str
    diffusion_index: float      # 扩散指数（上涨股票成交额占比）
    momentum: float             # 行业动量
    sdm_factor: float           # 扩散动量因子 = DI × Momentum
    volatility: float           # 年化波动率
    member_count: int           # 成分股数量
    up_count: int               # 上涨股票数量


class DiffusionMomentumStrategy:
    """扩散动量因子策略"""
    
    def __init__(self, db_path: str = 'quant_data.db'):
        self.db_path = db_path
        self.params = PARAMS
    
    def get_industries(self) -> List[Tuple[str, str]]:
        """获取行业列表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute('SELECT ts_code, name FROM ths_industries ORDER BY ts_code')
        industries = cursor.fetchall()
        conn.close()
        return industries
    
    def get_industry_members(self, industry_code: str) -> pd.DataFrame:
        """获取行业成分股"""
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql('''
            SELECT stock_code, name FROM ths_industry_members 
            WHERE industry_code = ?
        ''', conn, params=(industry_code,))
        conn.close()
        return df
    
    def get_stock_data(self, stock_code: str, end_date: str, days: int = 35) -> pd.DataFrame:
        """获取个股历史数据"""
        start_date = (datetime.strptime(end_date, '%Y%m%d') - timedelta(days=days)).strftime('%Y%m%d')
        
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql('''
            SELECT * FROM daily_prices 
            WHERE symbol = ? AND date >= ? AND date <= ?
            ORDER BY date
        ''', conn, params=(stock_code, start_date, end_date))
        conn.close()
        
        return df
    
    def get_industry_index_data(self, industry_code: str, end_date: str, days: int = 35) -> pd.DataFrame:
        """获取行业指数数据"""
        start_date = (datetime.strptime(end_date, '%Y%m%d') - timedelta(days=days)).strftime('%Y%m%d')
        
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql('''
            SELECT * FROM ths_industry_daily 
            WHERE ts_code = ? AND trade_date >= ? AND trade_date <= ?
            ORDER BY trade_date
        ''', conn, params=(industry_code, start_date, end_date))
        conn.close()
        
        return df
    
    def calculate_diffusion_momentum(self, industry_code: str, 
                                     trade_date: str) -> Optional[DiffusionSignal]:
        """
        计算扩散动量因子
        SDM = 扩散指数(DI) × 行业动量
        """
        industry_name = ''
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute('SELECT name FROM ths_industries WHERE ts_code = ?', (industry_code,))
        row = cursor.fetchone()
        if row:
            industry_name = row[0]
        conn.close()
        
        # 获取成分股
        members = self.get_industry_members(industry_code)
        if members.empty:
            logger.debug(f"{industry_code} 无成分股数据")
            return None
        
        total_weight = 0
        up_weight = 0
        up_count = 0
        valid_count = 0
        weighted_returns = []
        
        for _, row in members.iterrows():
            stock_code = row['stock_code']
            
            # 获取个股数据
            df = self.get_stock_data(stock_code, trade_date, days=45)
            if df.empty or len(df) < self.params['trend_period']:
                continue
            
            valid_count += 1
            
            # 计算30日涨跌幅
            recent_close = df['close'].iloc[-1]
            past_close = df['close'].iloc[-self.params['trend_period']]
            return_30d = (recent_close - past_close) / past_close
            
            # 计算成交额（近5日平均）
            avg_amount = df['amount'].tail(5).mean()
            
            # 累加权重
            total_weight += avg_amount
            
            # 判断是否超过阈值
            if return_30d > self.params['trend_threshold']:
                up_weight += avg_amount
                up_count += 1
            
            weighted_returns.append(avg_amount * return_30d)
        
        if total_weight == 0 or valid_count == 0:
            return None
        
        # 扩散指数 = 上涨股票成交额 / 总成交额
        diffusion_index = up_weight / total_weight
        
        # 行业动量 = 成交额加权平均涨跌幅
        industry_momentum = sum(weighted_returns) / total_weight
        
        # 扩散动量因子
        sdm = diffusion_index * industry_momentum
        
        # 计算波动率（用行业指数）
        index_df = self.get_industry_index_data(industry_code, trade_date)
        volatility = 0.2  # 默认值
        if not index_df.empty and len(index_df) > 10:
            returns = index_df['close'].pct_change().dropna()
            if len(returns) >= self.params['volatility_period']:
                volatility = returns.tail(self.params['volatility_period']).std() * np.sqrt(252)
        
        return DiffusionSignal(
            industry_code=industry_code,
            industry_name=industry_name,
            diffusion_index=diffusion_index,
            momentum=industry_momentum,
            sdm_factor=sdm,
            volatility=volatility,
            member_count=valid_count,
            up_count=up_count
        )
    
    def generate_signals(self, trade_date: str) -> List[DiffusionSignal]:
        """生成所有行业的信号"""
        industries = self.get_industries()
        signals = []
        
        logger.info(f"计算 {len(industries)} 个行业的扩散动量因子...")
        
        for i, (code, name) in enumerate(industries, 1):
            signal = self.calculate_diffusion_momentum(code, trade_date)
            if signal:
                signals.append(signal)
            
            if i % 20 == 0:
                logger.info(f"  进度: {i}/{len(industries)}")
        
        # 按SDM因子排序
        signals.sort(key=lambda x: x.sdm_factor, reverse=True)
        return signals
    
    def construct_portfolio(self, signals: List[DiffusionSignal]) -> Dict:
        """构建投资组合"""
        if not signals:
            return {'date': None, 'holdings': []}
        
        # 选择前N个
        top_signals = signals[:self.params['top_n']]
        
        # 风险平权
        inverse_vols = [1 / s.volatility for s in top_signals]
        total_inv_vol = sum(inverse_vols)
        
        holdings = []
        for i, signal in enumerate(top_signals):
            weight = inverse_vols[i] / total_inv_vol
            holdings.append({
                'industry_code': signal.industry_code,
                'industry_name': signal.industry_name,
                'weight': weight,
                'sdm_factor': signal.sdm_factor,
                'diffusion_index': signal.diffusion_index,
                'momentum': signal.momentum,
                'up_ratio': signal.up_count / signal.member_count if signal.member_count > 0 else 0
            })
        
        return {
            'date': trade_date,
            'top_n': self.params['top_n'],
            'holdings': holdings
        }
    
    def run(self, trade_date: str = None) -> Tuple[List[DiffusionSignal], Dict]:
        """运行策略"""
        if trade_date is None:
            trade_date = datetime.now().strftime('%Y%m%d')
        
        logger.info(f"=== 扩散动量因子策略 ({trade_date}) ===")
        
        # 生成信号
        signals = self.generate_signals(trade_date)
        
        # 构建组合
        portfolio = self.construct_portfolio(signals)
        
        return signals, portfolio
    
    def print_report(self, signals: List[DiffusionSignal], portfolio: Dict):
        """打印报告"""
        print(f"\n{'='*70}")
        print(f"扩散动量因子策略报告 - {portfolio['date']}")
        print(f"{'='*70}")
        
        print(f"\n参数设置:")
        print(f"  趋势判定周期: {self.params['trend_period']}日")
        print(f"  趋势阈值: {self.params['trend_threshold']:.1%}")
        print(f"  持仓数量: {self.params['top_n']}个行业")
        
        print(f"\n行业排名 (Top 15):")
        print(f"{'排名':<4} {'行业':<16} {'SDM因子':<12} {'扩散指数':<10} {'动量':<10} {'上涨占比':<10}")
        print("-" * 70)
        
        for i, s in enumerate(signals[:15], 1):
            up_ratio = s.up_count / s.member_count if s.member_count > 0 else 0
            print(f"{i:<4} {s.industry_name:<16} {s.sdm_factor:<12.6f} "
                  f"{s.diffusion_index:<10.4f} {s.momentum:<10.4f} {up_ratio:<10.1%}")
        
        print(f"\n推荐持仓:")
        print(f"{'行业':<16} {'权重':<10} {'SDM因子':<12} {'上涨占比':<10}")
        print("-" * 50)
        for h in portfolio['holdings']:
            print(f"{h['industry_name']:<16} {h['weight']:<10.2%} "
                  f"{h['sdm_factor']:<12.6f} {h['up_ratio']:<10.1%}")
        
        print(f"\n{'='*70}\n")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='扩散动量因子策略')
    parser.add_argument('--date', type=str, default=datetime.now().strftime('%Y%m%d'),
                       help='计算日期 (YYYYMMDD)')
    parser.add_argument('--db', type=str, default='quant_data.db',
                       help='数据库路径')
    parser.add_argument('--output', type=str, help='输出JSON文件路径')
    
    args = parser.parse_args()
    
    # 运行策略
    strategy = DiffusionMomentumStrategy(db_path=args.db)
    signals, portfolio = strategy.run(args.date)
    
    # 打印报告
    strategy.print_report(signals, portfolio)
    
    # 保存结果
    if args.output:
        output = {
            'strategy': 'DiffusionMomentum',
            'params': PARAMS,
            'date': args.date,
            'signals': [
                {
                    'industry_code': s.industry_code,
                    'industry_name': s.industry_name,
                    'sdm_factor': s.sdm_factor,
                    'diffusion_index': s.diffusion_index,
                    'momentum': s.momentum,
                    'volatility': s.volatility
                }
                for s in signals
            ],
            'portfolio': portfolio
        }
        
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        logger.info(f"结果已保存到: {args.output}")


if __name__ == '__main__':
    main()
