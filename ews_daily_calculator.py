#!/usr/bin/env python3
"""
情绪加权扩散动量因子 (EW-SDM) - 完整版 v5 (修正版)
修复：1) 炸板负反馈条件 2) 阈值比较Bug
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List
from dataclasses import dataclass, asdict
import json
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

PARAMS = {
    'trend_period': 5,
    'trend_threshold': 3.0,       # 修正：3%阈值（原为0.03，实际比较时放大了100倍）
    'max_leverage': 2.0,
    'sigmoid_offset': 3.5,
    'broken_drop_threshold': -5.0, # 新增：炸板负反馈跌幅阈值（%）
}


def init_tushare():
    import tushare as ts
    pro = ts.pro_api('75d5fb0d2da34ab076f1ab49eaecfac348aaf91faf06246bfcab9f68904c')
    pro._DataApi__token = '75d5fb0d2da34ab076f1ab49eaecfac348aaf91faf06246bfcab9f68904c'
    pro._DataApi__http_url = 'http://lianghua.nanyangqiankun.top'
    return pro


def calculate_emotion_weight(pct_chg: float, streak: int, is_broken: bool) -> float:
    """
    计算个股情绪权重
    
    规则：
    1. 炸板且跌幅超5% → -1.0（强负反馈）
    2. 无涨停：
       - 涨幅 > 3% → 1.0（主动上涨）
       - 涨幅 ≤ 3% → 0.0（不符合趋势）
    3. 首板 → 1.5
    4. 连板(n≥2) → 1.0 + 0.5 * n
    """
    # 炸板且大跌才算负反馈
    if is_broken and pct_chg < PARAMS['broken_drop_threshold']:
        return -1.0
    
    # 无涨停情况
    if streak <= 0:
        return 1.0 if pct_chg > PARAMS['trend_threshold'] else 0.0
    
    # 首板
    if streak == 1:
        return 1.5
    
    # 连板
    return 1.0 + 0.5 * streak


def calculate_ews_for_date(conn, trade_date: str, industries: pd.DataFrame, 
                           members_df: pd.DataFrame, daily_map: dict, 
                           prev_map: dict, limit_map: dict, fd_map: dict) -> List[dict]:
    """计算单日的EW-SDM"""
    signals = []
    
    for _, ind in industries.iterrows():
        industry_code = ind['ts_code']
        industry_name = ind['name']
        
        members = members_df[members_df['industry_code'] == industry_code]['stock_code'].tolist()
        if not members:
            continue
        
        total_stocks = len(members)
        up_count = 0
        total_weight = 0.0
        weighted_emotion = 0.0
        weighted_returns = []
        limit_up_count = 0
        broken_count = 0
        max_streak = 0
        
        for stock_code in members:
            daily_row = daily_map.get(stock_code)
            if daily_row is None:
                continue
            
            close = daily_row['close']
            amount = daily_row['amount']
            prev_close = prev_map.get(stock_code, 0)
            pct_chg = (close - prev_close) / prev_close * 100 if prev_close and prev_close > 0 else 0
            
            if pct_chg > 0:
                up_count += 1
            
            limit_row = limit_map.get(stock_code)
            streak = 0
            is_broken = False
            
            if limit_row is not None and limit_row['is_limit_up'] == 1:
                streak = int(limit_row['streak_count'])
                is_broken = limit_row['is_broken'] == 1
                max_streak = max(max_streak, streak)
                limit_up_count += 1
                if is_broken:
                    broken_count += 1
            
            fd_amount = fd_map.get(stock_code, 0)
            weight = amount + fd_amount
            
            # 修正后的情绪权重计算
            emotion_w = calculate_emotion_weight(pct_chg, streak, is_broken)
            
            total_weight += weight
            weighted_emotion += emotion_w * weight
            weighted_returns.append(weight * pct_chg)
        
        up_ratio = up_count / total_stocks if total_stocks > 0 else 0
        
        if total_weight > 0:
            emotion_diff = weighted_emotion / total_weight
            momentum = sum(weighted_returns) / total_weight
        else:
            emotion_diff = 0
            momentum = 0
        
        # S_score
        if max_streak <= 0:
            s_score = 1.0
        else:
            sigmoid = 1 / (1 + np.exp(-(max_streak - PARAMS['sigmoid_offset'])))
            s_score = PARAMS['max_leverage'] * sigmoid + 1
        
        final_score = momentum * emotion_diff * s_score
        
        detail = f"成分股{total_stocks}只, 上涨{up_count}只({up_ratio*100:.1f}%)"
        if limit_up_count > 0:
            detail += f", 涨停{limit_up_count}只"
            if broken_count > 0:
                detail += f"(炸{broken_count})"
            if max_streak > 0:
                detail += f", 最高{max_streak}连板"
        
        signals.append({
            'date': trade_date,
            'industry_code': industry_code,
            'industry_name': industry_name,
            'emotion_diff': round(emotion_diff, 4),
            'momentum': round(momentum, 4),
            's_score': round(s_score, 3),
            'final_score': round(final_score, 6),
            'max_streak': int(max_streak),
            'limit_up_count': limit_up_count,
            'broken_count': broken_count,
            'total_stocks': total_stocks,
            'up_ratio': round(up_ratio, 4),
            'detail': detail
        })
    
    signals.sort(key=lambda x: x['final_score'], reverse=True)
    for i, s in enumerate(signals, 1):
        s['rank'] = i
    
    return signals


def generate_stocks_for_date(conn, trade_date: str, industries: pd.DataFrame, members_df: pd.DataFrame) -> Dict:
    """生成单日成分股明细"""
    # 获取个股行情
    daily_df = pd.read_sql('SELECT symbol, close, amount FROM daily_prices WHERE date = ?', 
                           conn, params=(trade_date,))
    daily_map = {row['symbol']: {'close': row['close'], 'amount': row['amount']} 
                 for _, row in daily_df.iterrows()}
    
    # 获取前一日收盘价
    prev_date_row = pd.read_sql('''
        SELECT trade_date FROM ths_industry_daily 
        WHERE trade_date < ? ORDER BY trade_date DESC LIMIT 1
    ''', conn, params=(trade_date,))
    
    prev_map = {}
    if not prev_date_row.empty:
        prev_date = prev_date_row.iloc[0]['trade_date']
        prev_df = pd.read_sql('SELECT symbol, close FROM daily_prices WHERE date = ?', 
                              conn, params=(prev_date,))
        prev_map = {row['symbol']: row['close'] for _, row in prev_df.iterrows()}
    
    # 获取涨停数据
    limit_df = pd.read_sql('''
        SELECT ts_code, streak_count, is_broken, name
        FROM limit_streaks WHERE trade_date = ? AND is_limit_up = 1
    ''', conn, params=(trade_date,))
    limit_map = {row['ts_code']: row for _, row in limit_df.iterrows()}
    
    result = {}
    
    for _, ind in industries.iterrows():
        industry_code = ind['ts_code']
        members = members_df[members_df['industry_code'] == industry_code]['stock_code'].tolist()
        
        stocks = []
        for stock_code in members:
            daily_row = daily_map.get(stock_code)
            if not daily_row:
                continue
            
            close = daily_row['close']
            prev_close = prev_map.get(stock_code, 0)
            pct_chg = (close - prev_close) / prev_close * 100 if prev_close and prev_close > 0 else 0
            
            limit_row = limit_map.get(stock_code)
            streak = int(limit_row['streak_count']) if limit_row is not None else 0
            is_broken = limit_row['is_broken'] == 1 if limit_row is not None else False
            name = limit_row['name'] if limit_row is not None else stock_code
            
            # 计算情绪权重用于展示
            emotion_w = calculate_emotion_weight(pct_chg, streak, is_broken)
            
            stocks.append({
                'ts_code': stock_code,
                'name': name,
                'pct_chg': round(pct_chg, 2),
                'close': close,
                'streak': streak,
                'is_broken': is_broken,
                'emotion_weight': round(emotion_w, 2)  # 新增：显示情绪权重
            })
        
        stocks.sort(key=lambda x: x['pct_chg'], reverse=True)
        result[industry_code] = stocks
    
    return result


def main():
    db_path = Path(__file__).parent / 'data-collector' / 'quant_data.db'
    conn = sqlite3.connect(db_path)
    
    start_date = '20260101'
    end_date = '20260304'
    
    logger.info(f"=== 计算EW-SDM ({start_date} ~ {end_date}) ===")
    logger.info(f"参数: 趋势阈值={PARAMS['trend_threshold']}%, 炸板负反馈阈值={PARAMS['broken_drop_threshold']}%")
    
    # 预加载常用数据
    industries = pd.read_sql('SELECT ts_code, name FROM ths_industries', conn)
    logger.info(f"行业数: {len(industries)}")
    
    members_df = pd.read_sql('SELECT industry_code, stock_code FROM ths_industry_members', conn)
    logger.info(f"成分股关系数: {len(members_df)}")
    
    trade_dates = pd.read_sql('''
        SELECT DISTINCT trade_date FROM limit_streaks 
        WHERE trade_date >= ? AND trade_date <= ? ORDER BY trade_date
    ''', conn, params=(start_date, end_date))['trade_date'].tolist()
    
    logger.info(f"交易日数: {len(trade_dates)}")
    
    daily_results = {}
    stocks_data = {}
    
    for i, date in enumerate(trade_dates, 1):
        logger.info(f"[{i}/{len(trade_dates)}] 处理 {date}...")
        
        # 获取该日数据
        daily_df = pd.read_sql('SELECT symbol, close, amount FROM daily_prices WHERE date = ?', 
                               conn, params=(date,))
        daily_map = {row['symbol']: {'close': row['close'], 'amount': row['amount']} 
                     for _, row in daily_df.iterrows()}
        
        prev_date_row = pd.read_sql('''
            SELECT trade_date FROM ths_industry_daily 
            WHERE trade_date < ? ORDER BY trade_date DESC LIMIT 1
        ''', conn, params=(date,))
        
        prev_map = {}
        if not prev_date_row.empty:
            prev_date = prev_date_row.iloc[0]['trade_date']
            prev_df = pd.read_sql('SELECT symbol, close FROM daily_prices WHERE date = ?', 
                                  conn, params=(prev_date,))
            prev_map = {row['symbol']: row['close'] for _, row in prev_df.iterrows()}
        
        limit_df = pd.read_sql('''
            SELECT ts_code, streak_count, is_limit_up, is_broken, open_num, pct_chg, industry, name
            FROM limit_streaks WHERE trade_date = ?
        ''', conn, params=(date,))
        limit_map = {row['ts_code']: row for _, row in limit_df.iterrows()}
        
        fd_df = pd.read_sql('SELECT ts_code, fd_amount FROM limit_list_ths WHERE trade_date = ?', 
                            conn, params=(date,))
        fd_map = dict(zip(fd_df['ts_code'], fd_df['fd_amount'].fillna(0)))
        
        # 计算EW-SDM
        signals = calculate_ews_for_date(conn, date, industries, members_df, 
                                         daily_map, prev_map, limit_map, fd_map)
        daily_results[date] = signals
        logger.info(f"  行业信号: {len(signals)}")
        
        # 生成成分股数据
        stocks = generate_stocks_for_date(conn, date, industries, members_df)
        stocks_data[date] = stocks
        logger.info(f"  成分股数据: {len(stocks)} 个行业")
    
    conn.close()
    
    # 保存结果
    result = {
        'start_date': start_date,
        'end_date': end_date,
        'params': PARAMS,
        'daily_data': daily_results,
        'stocks_data': stocks_data
    }
    
    output_path = Path(__file__).parent / 'ews_daily_result.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    logger.info(f"\n完成！结果已保存到: {output_path}")
    logger.info(f"总交易日数: {len(daily_results)}")
    if daily_results:
        sample_date = list(daily_results.keys())[0]
        logger.info(f"样本日期 {sample_date}: {len(daily_results[sample_date])} 个行业")


if __name__ == '__main__':
    main()
