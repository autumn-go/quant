#!/usr/bin/env python3
"""
扩散动量因子策略 - 每日SDM计算
参数：5日趋势判定
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import json
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 策略参数
PARAMS = {
    'trend_period': 5,            # 趋势判定周期（5日）
    'trend_threshold': 0.03,      # 趋势判定阈值（3%）
}


@dataclass
class SDMSignal:
    """SDM信号"""
    date: str
    industry_code: str
    industry_name: str
    diffusion_index: float      # 扩散指数
    momentum: float             # 行业动量
    sdm_factor: float           # 扩散动量因子
    member_count: int           # 成分股数量
    up_count: int               # 上涨股票数量


class SDMDailyCalculator:
    """SDM每日计算器"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = str(Path(__file__).parent / 'data-collector' / 'quant_data.db')
        self.db_path = db_path
        self.params = PARAMS
    
    def get_industries(self) -> List[tuple]:
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
    
    def get_stock_data(self, stock_code: str, trade_date: str, days: int = 15) -> pd.DataFrame:
        """获取个股历史数据"""
        start_date = (datetime.strptime(trade_date, '%Y%m%d') - timedelta(days=days)).strftime('%Y%m%d')
        
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql('''
            SELECT * FROM daily_prices 
            WHERE symbol = ? AND date >= ? AND date <= ?
            ORDER BY date
        ''', conn, params=(stock_code, start_date, trade_date))
        conn.close()
        return df
    
    def calculate_sdm_for_industry(self, industry_code: str, industry_name: str, 
                                   trade_date: str) -> Optional[SDMSignal]:
        """计算单个行业某日的SDM"""
        # 获取成分股
        members = self.get_industry_members(industry_code)
        if members.empty:
            return None
        
        total_weight = 0
        up_weight = 0
        up_count = 0
        valid_count = 0
        weighted_returns = []
        
        for _, row in members.iterrows():
            stock_code = row['stock_code']
            
            # 获取个股数据
            df = self.get_stock_data(stock_code, trade_date, days=20)
            if df.empty or len(df) < self.params['trend_period'] + 1:
                continue
            
            valid_count += 1
            
            # 计算5日涨跌幅
            recent_close = df['close'].iloc[-1]
            past_close = df['close'].iloc[-self.params['trend_period'] - 1]
            return_5d = (recent_close - past_close) / past_close
            
            # 计算成交额（近3日平均）
            avg_amount = df['amount'].tail(3).mean()
            
            # 累加权重
            total_weight += avg_amount
            
            # 判断是否超过阈值
            if return_5d > self.params['trend_threshold']:
                up_weight += avg_amount
                up_count += 1
            
            weighted_returns.append(avg_amount * return_5d)
        
        if total_weight == 0 or valid_count == 0:
            return None
        
        # 扩散指数
        diffusion_index = up_weight / total_weight
        
        # 行业动量
        industry_momentum = sum(weighted_returns) / total_weight
        
        # 扩散动量因子
        sdm = diffusion_index * industry_momentum
        
        return SDMSignal(
            date=trade_date,
            industry_code=industry_code,
            industry_name=industry_name,
            diffusion_index=diffusion_index,
            momentum=industry_momentum,
            sdm_factor=sdm,
            member_count=valid_count,
            up_count=up_count
        )
    
    def calculate_daily_sdm(self, trade_date: str) -> List[SDMSignal]:
        """计算某日的所有行业SDM"""
        industries = self.get_industries()
        signals = []
        
        for code, name in industries:
            signal = self.calculate_sdm_for_industry(code, name, trade_date)
            if signal:
                signals.append(signal)
        
        # 按SDM倒序排序
        signals.sort(key=lambda x: x.sdm_factor, reverse=True)
        
        # 添加排名
        for i, signal in enumerate(signals, 1):
            signal.rank = i
        
        return signals
    
    def get_trade_dates(self, start_date: str, end_date: str) -> List[str]:
        """获取交易日列表（从行业指数数据中提取）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute('''
            SELECT DISTINCT trade_date FROM ths_industry_daily 
            WHERE trade_date >= ? AND trade_date <= ?
            ORDER BY trade_date
        ''', (start_date, end_date))
        dates = [row[0] for row in cursor.fetchall()]
        conn.close()
        return dates
    
    def run(self, start_date: str = '20260101', end_date: str = None) -> Dict:
        """
        运行每日SDM计算
        返回：{date: [SDMSignal列表]}
        """
        if end_date is None:
            end_date = datetime.now().strftime('%Y%m%d')
        
        logger.info(f"=== 计算每日SDM ({start_date} ~ {end_date}) ===")
        
        # 获取交易日
        trade_dates = self.get_trade_dates(start_date, end_date)
        logger.info(f"共 {len(trade_dates)} 个交易日")
        
        # 计算每日SDM
        daily_results = {}
        
        for i, date in enumerate(trade_dates, 1):
            logger.info(f"[{i}/{len(trade_dates)}] 计算 {date}...")
            signals = self.calculate_daily_sdm(date)
            daily_results[date] = [asdict(s) for s in signals]
        
        return {
            'start_date': start_date,
            'end_date': end_date,
            'params': self.params,
            'daily_data': daily_results
        }


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='SDM每日计算器')
    parser.add_argument('--start', type=str, default='20260101',
                       help='开始日期 (YYYYMMDD)')
    parser.add_argument('--end', type=str, default='20260304',
                       help='结束日期 (YYYYMMDD)')
    parser.add_argument('--db', type=str, default=None,
                       help='数据库路径')
    parser.add_argument('--output', type=str, default='sdm_daily_result.json',
                       help='输出JSON文件')
    
    args = parser.parse_args()
    
    # 运行计算
    calculator = SDMDailyCalculator(db_path=args.db)
    result = calculator.run(args.start, args.end)
    
    # 保存结果
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    logger.info(f"结果已保存到: {args.output}")
    logger.info(f"总交易日数: {len(result['daily_data'])}")


if __name__ == '__main__':
    main()
