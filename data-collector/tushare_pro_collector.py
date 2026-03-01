#!/usr/bin/env python3
"""
Tushare Pro 数据采集器 - 使用购买的Token
支持：个股、指数、ETF
"""

import tushare as ts
import sqlite3
from datetime import datetime, timedelta
import time
import argparse

# Tushare Token
TOKEN = 'fb3c079912502be08b6fc877031219159d9fcac540ca83f77974ed7714d4'
DB_PATH = 'quant_data.db'

def init_tushare():
    """初始化Tushare"""
    pro = ts.pro_api(TOKEN)
    pro._DataApi__token = TOKEN
    pro._DataApi__http_url = 'http://lianghua.nanyangqiankun.top'
    return pro

def init_db():
    """初始化数据库"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 股票列表表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stocks (
            symbol TEXT PRIMARY KEY,
            code TEXT NOT NULL,
            name TEXT,
            exchange TEXT,
            market TEXT,
            market_type TEXT,
            industry TEXT,
            list_date TEXT
        )
    ''')
    
    # 日线数据表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_prices (
            symbol TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            amount REAL,
            change REAL,
            pct_chg REAL,
            PRIMARY KEY (symbol, date)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("[INFO] 数据库初始化完成")

def fetch_stock_list(pro):
    """获取股票列表"""
    import pandas as pd
    print("[INFO] 获取股票列表...")
    df = pro.stock_basic(exchange='', list_status='L', 
                         fields='ts_code,symbol,name,area,industry,list_date,market,exchange')
    
    stocks = []
    for _, row in df.iterrows():
        # 转换代码格式
        ts_code = row['ts_code']  # 000001.SZ
        exchange = 'SZ' if ts_code.endswith('.SZ') else 'SH'
        
        market_type = row['market'] if pd.notna(row['market']) else ''
        
        stocks.append((
            ts_code,
            row['symbol'],
            row['name'],
            exchange,
            'A股',
            market_type,
            row['industry'] if pd.notna(row['industry']) else '',
            row['list_date'] if pd.notna(row['list_date']) else ''
        ))
    
    print(f"[INFO] 获取到 {len(stocks)} 只股票")
    return stocks

def save_stocks(stocks):
    """保存股票列表"""
    conn = sqlite3.connect(DB_PATH)
    for s in stocks:
        conn.execute('INSERT OR REPLACE INTO stocks VALUES (?,?,?,?,?,?,?,?)', s)
    conn.commit()
    conn.close()
    print(f"[INFO] 保存了 {len(stocks)} 只股票")

def fetch_daily(pro, ts_code, start_date, end_date):
    """获取日线数据"""
    import pandas as pd
    try:
        df = pro.daily(ts_code=ts_code, start_date=start_date.replace('-', ''), 
                      end_date=end_date.replace('-', ''))
        
        if df is None or df.empty:
            return []
        
        data = []
        for _, row in df.iterrows():
            data.append((
                ts_code,
                row['trade_date'],
                float(row['open']) if pd.notna(row['open']) else 0,
                float(row['high']) if pd.notna(row['high']) else 0,
                float(row['low']) if pd.notna(row['low']) else 0,
                float(row['close']) if pd.notna(row['close']) else 0,
                float(row['vol']) if pd.notna(row['vol']) else 0,
                float(row['amount']) if pd.notna(row['amount']) else 0,
                float(row['change']) if pd.notna(row['change']) else 0,
                float(row['pct_chg']) if pd.notna(row['pct_chg']) else 0
            ))
        return data
    except Exception as e:
        print(f"[ERROR] 获取 {ts_code} 失败: {e}")
        return []

def get_last_date(symbol):
    """获取最后更新日期"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute('SELECT MAX(date) FROM daily_prices WHERE symbol = ?', (symbol,))
    result = cursor.fetchone()[0]
    conn.close()
    return result

def save_daily(data):
    """保存日线数据"""
    if not data:
        return 0
    
    conn = sqlite3.connect(DB_PATH)
    count = 0
    for row in data:
        try:
            conn.execute('INSERT OR IGNORE INTO daily_prices VALUES (?,?,?,?,?,?,?,?,?,?)', row)
            count += 1
        except:
            pass
    conn.commit()
    conn.close()
    return count

def collect_stocks(pro, symbols, limit=None):
    """采集股票数据"""
    if limit:
        symbols = symbols[:limit]
    
    print(f"\n开始采集 {len(symbols)} 只股票...")
    
    success = 0
    total = 0
    start_time = time.time()
    
    for i, symbol in enumerate(symbols):
        last = get_last_date(symbol)
        if last:
            start = (datetime.strptime(last, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
        else:
            start = '20140101'
        
        end = datetime.now().strftime('%Y%m%d')
        
        if start > end:
            continue
        
        data = fetch_daily(pro, symbol, start, end)
        count = save_daily(data)
        
        if count > 0:
            success += 1
            total += count
        
        if (i + 1) % 10 == 0:
            elapsed = time.time() - start_time
            print(f"  [{i+1}/{len(symbols)}] 成功:{success} 记录:{total:,} 已用:{elapsed/60:.1f}分", flush=True)
        
        time.sleep(0.05)  # 限速
    
    elapsed = time.time() - start_time
    print(f"\n完成! 成功:{success} 总记录:{total:,} 用时:{elapsed/60:.1f}分")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--init', action='store_true', help='初始化股票列表')
    parser.add_argument('--full', action='store_true', help='全量采集')
    parser.add_argument('--limit', type=int, help='限制数量')
    args = parser.parse_args()
    
    import pandas as pd  # 延迟导入
    
    init_db()
    pro = init_tushare()
    
    if args.init:
        stocks = fetch_stock_list(pro)
        save_stocks(stocks)
    
    if args.full:
        conn = sqlite3.connect(DB_PATH)
        symbols = [row[0] for row in conn.execute('SELECT symbol FROM stocks')]
        conn.close()
        collect_stocks(pro, symbols, args.limit)

if __name__ == '__main__':
    main()
