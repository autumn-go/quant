#!/usr/bin/env python3
"""
同花顺涨跌停数据采集器 - 完整修复版
使用Tushare接口: limit_list_ths
修复：保存open_num（炸板次数）字段
"""

import tushare as ts
import sqlite3
import pandas as pd
from datetime import datetime
from typing import List, Optional
import logging
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TOKEN = '75d5fb0d2da34ab076f1ab49eaecfac348aaf91faf06246bfcab9f68904c'
DB_PATH = 'quant_data.db'


def init_tushare():
    pro = ts.pro_api(TOKEN)
    pro._DataApi__token = TOKEN
    pro._DataApi__http_url = 'http://lianghua.nanyangqiankun.top'
    return pro


def init_db():
    """初始化数据库表 - 添加open_num字段"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 删除旧表重新创建（确保字段正确）
    cursor.execute('DROP TABLE IF EXISTS limit_list_ths')
    cursor.execute('DROP TABLE IF EXISTS limit_streaks')
    
    # 涨跌停榜单表
    cursor.execute('''
        CREATE TABLE limit_list_ths (
            trade_date TEXT NOT NULL,
            ts_code TEXT NOT NULL,
            name TEXT,
            close REAL,
            pct_chg REAL,
            open_num INTEGER,          -- 炸板次数
            amount REAL,
            limit_amount REAL,
            float_mv REAL,
            total_mv REAL,
            turnover_ratio REAL,
            fd_amount REAL,
            first_time TEXT,
            last_time TEXT,
            up_stat TEXT,
            limit_type TEXT,
            industry TEXT,
            lu_limit_order REAL,
            limit_up_suc_rate REAL,
            market_type TEXT,
            PRIMARY KEY (trade_date, ts_code)
        )
    ''')
    
    # 连板统计表
    cursor.execute('''
        CREATE TABLE limit_streaks (
            trade_date TEXT NOT NULL,
            ts_code TEXT NOT NULL,
            name TEXT,
            streak_count INTEGER,
            is_limit_up INTEGER,
            is_limit_down INTEGER,
            is_broken INTEGER,
            open_num INTEGER,          -- 炸板次数
            first_limit_time TEXT,
            last_limit_time TEXT,
            limit_type TEXT,
            industry TEXT,
            pct_chg REAL,
            PRIMARY KEY (trade_date, ts_code)
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("数据库表初始化完成")


def get_trade_dates(start_date: str, end_date: str) -> List[str]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute('''
        SELECT DISTINCT trade_date FROM ths_industry_daily 
        WHERE trade_date >= ? AND trade_date <= ?
        ORDER BY trade_date
    ''', (start_date, end_date))
    dates = [row[0] for row in cursor.fetchall()]
    conn.close()
    return dates


def collect_limit_list(pro, trade_date: str) -> Optional[pd.DataFrame]:
    """采集某日的涨跌停数据"""
    try:
        df = pro.limit_list_ths(trade_date=trade_date)
        
        if df is None or df.empty:
            logger.warning(f"{trade_date} 无涨跌停数据")
            return None
        
        # 重命名列 - 保留open_num
        column_map = {
            'trade_date': 'trade_date',
            'ts_code': 'ts_code',
            'name': 'name',
            'price': 'close',
            'pct_chg': 'pct_chg',
            'open_num': 'open_num',        # 炸板次数
            'turnover': 'amount',
            'limit_amount': 'limit_amount',
            'free_float': 'float_mv',
            'turnover_rate': 'turnover_ratio',
            'lu_limit_order': 'lu_limit_order',
            'limit_up_suc_rate': 'limit_up_suc_rate',
            'market_type': 'market_type',
            'limit_order': 'fd_amount',
            'first_time': 'first_time',
            'last_time': 'last_time',
            'up_stat': 'up_stat',
            'limit_type': 'limit_type',
            'tag': 'industry'
        }
        
        df = df.rename(columns=column_map)
        
        # 填充缺失值
        for col in ['total_mv', 'fd_amount', 'open_num']:
            if col not in df.columns:
                df[col] = 0
            else:
                df[col] = df[col].fillna(0)
        
        for col in ['first_time', 'last_time', 'up_stat', 'industry']:
            if col not in df.columns:
                df[col] = None
        
        df['trade_date'] = df['trade_date'].astype(str)
        
        logger.info(f"{trade_date} 采集到 {len(df)} 条数据")
        return df
        
    except Exception as e:
        logger.error(f"{trade_date} 采集失败: {e}")
        return None


def save_limit_list(df: pd.DataFrame):
    """保存涨跌停数据"""
    if df is None or df.empty:
        return
    
    conn = sqlite3.connect(DB_PATH)
    
    columns = ['trade_date', 'ts_code', 'name', 'close', 'pct_chg', 'open_num',
               'amount', 'limit_amount', 'float_mv', 'total_mv', 'turnover_ratio', 
               'fd_amount', 'first_time', 'last_time', 'up_stat', 'limit_type', 
               'industry', 'lu_limit_order', 'limit_up_suc_rate', 'market_type']
    
    # 只保留存在的列
    existing_columns = [c for c in columns if c in df.columns]
    df_to_save = df[existing_columns].copy()
    
    df_to_save.to_sql('limit_list_ths', conn, if_exists='append', index=False)
    
    conn.close()
    logger.info(f"保存了 {len(df_to_save)} 条数据")


def calculate_streaks(trade_date: str):
    """计算连板天数和炸板标识 - 使用open_num判断炸板"""
    conn = sqlite3.connect(DB_PATH)
    
    df = pd.read_sql('SELECT * FROM limit_list_ths WHERE trade_date = ?', conn, params=(trade_date,))
    
    if df.empty:
        conn.close()
        return
    
    streak_records = []
    
    for _, row in df.iterrows():
        ts_code = row['ts_code']
        name = row['name']
        pct_chg = row['pct_chg'] if pd.notna(row.get('pct_chg', None)) else 0
        open_num = int(row['open_num']) if pd.notna(row.get('open_num', None)) else 0
        first_time = row.get('first_time', None)
        last_time = row.get('last_time', None)
        industry = row.get('industry', None)
        limit_type = row.get('limit_type', '')
        
        # 判断涨停/跌停：涨幅>=9%视为涨停
        is_limit_up = 1 if pct_chg >= 9.0 else 0
        is_limit_down = 1 if pct_chg <= -9.0 else 0
        
        # 判断炸板：open_num > 0 表示炸板
        is_broken = 1 if open_num > 0 else 0
        
        # 计算连板天数
        streak_count = 0
        
        if is_limit_up:
            streak_count = 1
            check_date = trade_date
            streak = 0
            max_check = 20
            
            while max_check > 0:
                max_check -= 1
                
                prev_date_row = pd.read_sql('''
                    SELECT trade_date FROM ths_industry_daily 
                    WHERE trade_date < ? ORDER BY trade_date DESC LIMIT 1
                ''', conn, params=(check_date,))
                
                if prev_date_row.empty:
                    break
                
                prev_date = prev_date_row.iloc[0]['trade_date']
                
                prev_limit = pd.read_sql('''
                    SELECT pct_chg FROM limit_list_ths 
                    WHERE trade_date = ? AND ts_code = ? AND pct_chg >= 9.0
                ''', conn, params=(prev_date, ts_code))
                
                if prev_limit.empty:
                    break
                
                streak += 1
                check_date = prev_date
            
            streak_count = streak + 1
        
        streak_records.append({
            'trade_date': trade_date,
            'ts_code': ts_code,
            'name': name,
            'streak_count': streak_count,
            'is_limit_up': is_limit_up,
            'is_limit_down': is_limit_down,
            'is_broken': is_broken,
            'open_num': open_num,
            'first_limit_time': first_time,
            'last_limit_time': last_time,
            'limit_type': limit_type,
            'industry': industry,
            'pct_chg': pct_chg
        })
    
    if streak_records:
        streak_df = pd.DataFrame(streak_records)
        streak_df.to_sql('limit_streaks', conn, if_exists='append', index=False)
        logger.info(f"{trade_date} 计算了 {len(streak_records)} 条连板数据")
    
    conn.close()


def run_collection(start_date: str = '20260101', end_date: str = None):
    if end_date is None:
        end_date = datetime.now().strftime('%Y%m%d')
    
    logger.info(f"=== 开始采集涨跌停数据 ({start_date} ~ {end_date}) ===")
    
    init_db()
    pro = init_tushare()
    
    trade_dates = get_trade_dates(start_date, end_date)
    logger.info(f"共 {len(trade_dates)} 个交易日")
    
    for i, date in enumerate(trade_dates, 1):
        logger.info(f"[{i}/{len(trade_dates)}] 采集 {date}...")
        
        df = collect_limit_list(pro, date)
        if df is not None:
            save_limit_list(df)
            calculate_streaks(date)
        
        time.sleep(0.3)
    
    logger.info("=== 数据采集完成 ===")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='同花顺涨跌停数据采集器-完整修复版')
    parser.add_argument('--start', type=str, default='20260101')
    parser.add_argument('--end', type=str, default=None)
    
    args = parser.parse_args()
    
    run_collection(args.start, args.end)
