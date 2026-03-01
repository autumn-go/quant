#!/usr/bin/env python3
import tushare as ts
import sqlite3
from datetime import datetime, timedelta
import time

TOKEN = '75d5fb0d2da34ab076f1ab49eaecfac348aaf91faf06246bfcab9f68904c'
DB_PATH = "quant_data.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS stocks (symbol TEXT PRIMARY KEY, code TEXT, name TEXT, exchange TEXT, market TEXT, market_type TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS daily_prices (symbol TEXT, date TEXT, open REAL, high REAL, low REAL, close REAL, volume REAL, amount REAL, PRIMARY KEY (symbol, date))')
    conn.commit()
    conn.close()
    print("[INFO] 数据库初始化完成")

def main():
    init_db()
    
    # 初始化 Tushare
    pro = ts.pro_api(TOKEN)
    pro._DataApi__token = TOKEN
    pro._DataApi__http_url = 'http://lianghua.nanyangqiankun.top'
    
    print("[INFO] 开始采集...")
    
    # 获取股票列表
    df = pro.stock_basic(exchange='', list_status='L', fields='ts_code,symbol,name,exchange')
    stocks = df['ts_code'].tolist()
    print(f"[INFO] 共 {len(stocks)} 只股票")
    
    # 采集数据
    conn = sqlite3.connect(DB_PATH)
    start_time = time.time()
    
    for i, symbol in enumerate(stocks[:100]):  # 先采集100只测试
        try:
            df = pro.daily(ts_code=symbol, start_date='20140101', end_date='20260227')
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    conn.execute('INSERT OR IGNORE INTO daily_prices VALUES (?,?,?,?,?,?,?,?)',
                        (symbol, row['trade_date'], row['open'], row['high'], row['low'], row['close'], row['vol'], row['amount']))
                conn.commit()
            
            if (i+1) % 10 == 0:
                print(f"  [{i+1}/100] 已用 {(time.time()-start_time)/60:.1f} 分")
            time.sleep(0.05)
        except Exception as e:
            print(f"[ERROR] {symbol}: {e}")
    
    conn.close()
    print("[INFO] 完成!")

if __name__ == '__main__':
    main()
