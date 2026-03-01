#!/usr/bin/env python3
"""
ETF 数据采集器 - 采集最近两个月所有ETF日行情数据
使用 Tushare Pro API
"""

import tushare as ts
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import time
import os
import sys

# Tushare Token
TOKEN = 'fb3c079912502be08b6fc877031219159d9fcac540ca83f77974ed7714d4'
DB_PATH = "etf_data.db"

# 计算日期范围
END_DATE = datetime.now().strftime('%Y%m%d')
START_DATE = (datetime.now() - timedelta(days=70)).strftime('%Y%m%d')  # 约2个月

print(f"数据时间范围: {START_DATE} 至 {END_DATE}")


def init_db():
    """初始化数据库"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # ETF基础信息表
    c.execute('''CREATE TABLE IF NOT EXISTS etf_list (
        ts_code TEXT PRIMARY KEY,
        symbol TEXT,
        name TEXT,
        exchange TEXT,
        market TEXT
    )''')
    
    # ETF日线数据表
    c.execute('''CREATE TABLE IF NOT EXISTS etf_daily (
        ts_code TEXT,
        trade_date TEXT,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        pre_close REAL,
        change REAL,
        pct_chg REAL,
        vol REAL,
        amount REAL,
        PRIMARY KEY (ts_code, trade_date)
    )''')
    
    conn.commit()
    conn.close()
    print("[INFO] 数据库初始化完成")


def fetch_etf_list(pro):
    """获取所有ETF列表"""
    print("[INFO] 正在获取ETF列表...")
    
    # 获取上海ETF
    df_sh = pro.fund_basic(market='E', exchange='SSE')
    # 获取深圳ETF
    df_sz = pro.fund_basic(market='E', exchange='SZSE')
    
    # 合并
    df = pd.concat([df_sh, df_sz], ignore_index=True)
    
    # 筛选ETF
    df = df[df['name'].str.contains('ETF', na=False)]
    
    print(f"[INFO] 共获取 {len(df)} 只ETF")
    return df


def save_etf_list(df):
    """保存ETF列表到数据库"""
    conn = sqlite3.connect(DB_PATH)
    
    for _, row in df.iterrows():
        # 从 ts_code 提取 symbol (如 510050.SH -> 510050)
        symbol = row['ts_code'].split('.')[0] if '.' in str(row['ts_code']) else row['ts_code']
        conn.execute('''INSERT OR REPLACE INTO etf_list 
            (ts_code, symbol, name, exchange, market)
            VALUES (?, ?, ?, ?, ?)''',
            (row['ts_code'], symbol, row.get('name', ''), 
             row.get('exchange', ''), 'ETF')
        )
    
    conn.commit()
    conn.close()
    print(f"[INFO] 已保存 {len(df)} 只ETF到数据库")


def fetch_etf_daily(pro, ts_code, start_date, end_date):
    """获取单只ETF日线数据"""
    try:
        df = pro.fund_daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
        return df
    except Exception as e:
        print(f"[ERROR] 获取 {ts_code} 数据失败: {e}")
        return pd.DataFrame()


def save_etf_daily(df):
    """保存ETF日线数据"""
    if df.empty:
        return 0
    
    conn = sqlite3.connect(DB_PATH)
    count = 0
    
    for _, row in df.iterrows():
        try:
            conn.execute('''INSERT OR REPLACE INTO etf_daily 
                (ts_code, trade_date, open, high, low, close, pre_close, 
                 change, pct_chg, vol, amount)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (row['ts_code'], row['trade_date'], row['open'], row['high'],
                 row['low'], row['close'], row.get('pre_close', 0),
                 row.get('change', 0), row.get('pct_chg', 0),
                 row['vol'], row['amount'])
            )
            count += 1
        except Exception as e:
            print(f"[ERROR] 保存数据失败: {e}")
    
    conn.commit()
    conn.close()
    return count


def main():
    print("=" * 60)
    print("ETF 数据采集器")
    print("=" * 60)
    
    # 初始化数据库
    init_db()
    
    # 初始化 Tushare
    ts.set_token(TOKEN)
    pro = ts.pro_api()
    pro._DataApi__token = TOKEN
    pro._DataApi__http_url = 'http://lianghua.nanyangqiankun.top'
    
    # 获取ETF列表
    etf_df = fetch_etf_list(pro)
    save_etf_list(etf_df)
    
    # 获取所有ETF代码
    etf_codes = etf_df['ts_code'].tolist()
    
    print(f"\n[INFO] 开始采集 {len(etf_codes)} 只ETF的日线数据...")
    print(f"[INFO] 时间范围: {START_DATE} 至 {END_DATE}")
    print("=" * 60)
    
    # 采集数据
    total_records = 0
    success_count = 0
    fail_count = 0
    
    for i, ts_code in enumerate(etf_codes):
        try:
            df = fetch_etf_daily(pro, ts_code, START_DATE, END_DATE)
            if not df.empty:
                count = save_etf_daily(df)
                total_records += count
                success_count += 1
                print(f"[{i+1}/{len(etf_codes)}] {ts_code}: {count} 条记录")
            else:
                fail_count += 1
                print(f"[{i+1}/{len(etf_codes)}] {ts_code}: 无数据")
            
            # 限速，避免触发限流
            time.sleep(0.05)
            
        except Exception as e:
            fail_count += 1
            print(f"[{i+1}/{len(etf_codes)}] {ts_code}: 失败 - {e}")
            continue
    
    print("\n" + "=" * 60)
    print("采集完成!")
    print(f"成功: {success_count}, 失败: {fail_count}")
    print(f"总记录数: {total_records}")
    print("=" * 60)
    
    # 显示统计
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute('SELECT COUNT(DISTINCT ts_code) FROM etf_daily')
    etf_with_data = cursor.fetchone()[0]
    cursor = conn.execute('SELECT COUNT(*) FROM etf_daily')
    total = cursor.fetchone()[0]
    conn.close()
    
    print(f"\n数据统计:")
    print(f"  有数据的ETF: {etf_with_data} 只")
    print(f"  总记录数: {total} 条")


if __name__ == '__main__':
    main()
