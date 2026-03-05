#!/usr/bin/env python3
"""
Tushare Pro 数据采集器 - 扩展版
支持：个股、指数、ETF、同花顺行业数据
新增：ths_member（行业成分股）、ths_daily（行业指数）
"""

import tushare as ts
import sqlite3
from datetime import datetime, timedelta
import time
import argparse
import pandas as pd

# Tushare Token
TOKEN = '75d5fb0d2da34ab076f1ab49eaecfac348aaf91faf06246bfcab9f68904c'
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
    
    # 日线数据表（个股/指数/ETF）
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
    
    # 同花顺行业列表表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ths_industries (
            ts_code TEXT PRIMARY KEY,
            name TEXT,
            count INTEGER,
            exchange TEXT,
            list_date TEXT,
            type TEXT,
            updated_at TEXT
        )
    ''')
    
    # 同花顺行业成分股表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ths_industry_members (
            industry_code TEXT,
            stock_code TEXT,
            name TEXT,
            updated_at TEXT,
            PRIMARY KEY (industry_code, stock_code)
        )
    ''')
    
    # 同花顺行业指数日线表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ths_industry_daily (
            ts_code TEXT,
            trade_date TEXT,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            amount REAL,
            pct_chg REAL,
            PRIMARY KEY (ts_code, trade_date)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("[INFO] 数据库初始化完成")

# ==================== 原有功能：个股数据 ====================

def fetch_stock_list(pro):
    """获取股票列表"""
    print("[INFO] 获取股票列表...")
    df = pro.stock_basic(exchange='', list_status='L', 
                         fields='ts_code,symbol,name,area,industry,list_date,market,exchange')
    
    stocks = []
    for _, row in df.iterrows():
        ts_code = row['ts_code']
        exchange = 'SZ' if ts_code.endswith('.SZ') else 'SH'
        market_type = row['market'] if pd.notna(row['market']) else ''
        
        stocks.append((
            ts_code, row['symbol'], row['name'], exchange, 'A股',
            market_type, row['industry'] if pd.notna(row['industry']) else '',
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
    try:
        df = pro.daily(ts_code=ts_code, start_date=start_date.replace('-', ''), 
                      end_date=end_date.replace('-', ''))
        
        if df is None or df.empty:
            return []
        
        data = []
        for _, row in df.iterrows():
            data.append((
                ts_code, row['trade_date'],
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

def get_last_date(symbol, table='daily_prices'):
    """获取最后更新日期"""
    conn = sqlite3.connect(DB_PATH)
    if table == 'daily_prices':
        cursor = conn.execute('SELECT MAX(date) FROM daily_prices WHERE symbol = ?', (symbol,))
    else:
        cursor = conn.execute(f'SELECT MAX(trade_date) FROM {table} WHERE ts_code = ?', (symbol,))
    result = cursor.fetchone()[0]
    conn.close()
    return result

def save_daily(data, table='daily_prices'):
    """保存日线数据"""
    if not data:
        return 0
    
    conn = sqlite3.connect(DB_PATH)
    count = 0
    for row in data:
        try:
            if table == 'daily_prices':
                conn.execute('INSERT OR IGNORE INTO daily_prices VALUES (?,?,?,?,?,?,?,?,?,?)', row)
            else:
                # ths_industry_daily: ts_code, trade_date, open, high, low, close, volume, amount, pct_chg
                conn.execute('INSERT OR IGNORE INTO ths_industry_daily VALUES (?,?,?,?,?,?,?,?,?)', row)
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
        
        time.sleep(0.05)
    
    elapsed = time.time() - start_time
    print(f"\n完成! 成功:{success} 总记录:{total:,} 用时:{elapsed/60:.1f}分")

# ==================== 新增功能：同花顺行业数据 ====================

def import_ths_industries(csv_path):
    """从CSV导入同花顺行业列表"""
    print(f"[INFO] 从 {csv_path} 导入行业列表...")
    df = pd.read_csv(csv_path)
    
    conn = sqlite3.connect(DB_PATH)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    count = 0
    
    for _, row in df.iterrows():
        try:
            conn.execute('''
                INSERT OR REPLACE INTO ths_industries 
                (ts_code, name, count, exchange, list_date, type, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (row['ts_code'], row['name'], 
                  row['count'] if pd.notna(row['count']) else 0,
                  row['exchange'], row['list_date'], row['type'], now))
            count += 1
        except Exception as e:
            print(f"[WARN] 导入 {row['ts_code']} 失败: {e}")
    
    conn.commit()
    conn.close()
    print(f"[INFO] 导入了 {count} 个行业")

def collect_ths_members(pro, refresh=False):
    """
    采集同花顺行业成分股
    接口: ths_member
    """
    conn = sqlite3.connect(DB_PATH)
    industries = conn.execute('SELECT ts_code, name FROM ths_industries').fetchall()
    conn.close()
    
    print(f"\n开始采集 {len(industries)} 个行业的成分股...")
    
    success = 0
    failed = 0
    
    for i, (ts_code, name) in enumerate(industries, 1):
        # 检查是否已有数据
        if not refresh:
            conn = sqlite3.connect(DB_PATH)
            count = conn.execute(
                'SELECT COUNT(*) FROM ths_industry_members WHERE industry_code = ?',
                (ts_code,)
            ).fetchone()[0]
            conn.close()
            if count > 0:
                continue
        
        try:
            df = pro.ths_member(ts_code=ts_code)
            
            if df is not None and not df.empty:
                # ths_member返回的列名: con_code, con_name
                df = df[['con_code', 'con_name']].copy()
                df.columns = ['stock_code', 'name']
                
                conn = sqlite3.connect(DB_PATH)
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                for _, row in df.iterrows():
                    conn.execute('''
                        INSERT OR REPLACE INTO ths_industry_members 
                        (industry_code, stock_code, name, updated_at)
                        VALUES (?, ?, ?, ?)
                    ''', (ts_code, row['stock_code'], row['name'], now))
                
                conn.commit()
                conn.close()
                success += 1
                
                if success % 10 == 0:
                    print(f"  [{i}/{len(industries)}] 已采集 {success} 个行业")
            else:
                failed += 1
            
            time.sleep(0.1)
            
        except Exception as e:
            failed += 1
            if failed % 10 == 0:
                print(f"  [WARN] 最近10个失败，当前: {name} - {e}")
            time.sleep(0.3)
    
    print(f"\n完成! 成功:{success} 失败:{failed}")

def collect_ths_daily(pro, start_date, end_date, refresh=False):
    """
    采集同花顺行业指数日线
    接口: ths_daily
    """
    conn = sqlite3.connect(DB_PATH)
    industries = conn.execute('SELECT ts_code, name FROM ths_industries').fetchall()
    conn.close()
    
    print(f"\n开始采集 {len(industries)} 个行业指数的价格数据...")
    
    success = 0
    total_records = 0
    
    for i, (ts_code, name) in enumerate(industries, 1):
        try:
            # 检查最新日期
            if not refresh:
                conn = sqlite3.connect(DB_PATH)
                last_date = conn.execute(
                    'SELECT MAX(trade_date) FROM ths_industry_daily WHERE ts_code = ?',
                    (ts_code,)
                ).fetchone()[0]
                conn.close()
                
                if last_date and last_date >= end_date:
                    continue
                elif last_date:
                    start = (datetime.strptime(last_date, '%Y%m%d') + timedelta(days=1)).strftime('%Y%m%d')
                else:
                    start = start_date
            else:
                start = start_date
            
            if start > end_date:
                continue
            
            df = pro.ths_daily(ts_code=ts_code, start_date=start, end_date=end_date)
            
            if df is not None and not df.empty:
                data = []
                for _, row in df.iterrows():
                    data.append((
                        row['ts_code'], row['trade_date'],
                        float(row['open']), float(row['high']), float(row['low']),
                        float(row['close']), float(row['vol']),
                        float(row['amount']), float(row.get('pct_chg', 0))
                    ))
                
                count = save_daily(data, table='ths_industry_daily')
                success += 1
                total_records += count
                
                if success % 10 == 0:
                    print(f"  [{i}/{len(industries)}] 已采集 {success} 个行业, 共 {total_records} 条")
            
            time.sleep(0.1)
            
        except Exception as e:
            if i % 20 == 0:
                print(f"  [WARN] 采集 {name} 失败: {e}")
            time.sleep(0.3)
    
    print(f"\n完成! 成功:{success} 个行业, 共 {total_records} 条记录")

# ==================== 主函数 ====================

def main():
    parser = argparse.ArgumentParser(description='Tushare Pro 数据采集器')
    
    # 原有功能
    parser.add_argument('--init', action='store_true', help='初始化股票列表')
    parser.add_argument('--full', action='store_true', help='全量采集个股数据')
    parser.add_argument('--limit', type=int, help='限制数量')
    
    # 新增功能
    parser.add_argument('--import-ths', type=str, help='导入同花顺行业CSV')
    parser.add_argument('--ths-members', action='store_true', help='采集行业成分股')
    parser.add_argument('--ths-daily', action='store_true', help='采集行业指数日线')
    
    # 通用参数
    parser.add_argument('--refresh', action='store_true', help='强制刷新')
    parser.add_argument('--start-date', type=str, default='20240101', help='开始日期')
    parser.add_argument('--end-date', type=str, default=datetime.now().strftime('%Y%m%d'), help='结束日期')
    
    args = parser.parse_args()
    
    init_db()
    pro = init_tushare()
    
    # 原有功能
    if args.init:
        stocks = fetch_stock_list(pro)
        save_stocks(stocks)
    
    if args.full:
        conn = sqlite3.connect(DB_PATH)
        symbols = [row[0] for row in conn.execute('SELECT symbol FROM stocks')]
        conn.close()
        collect_stocks(pro, symbols, args.limit)
    
    # 新增功能
    if args.import_ths:
        import_ths_industries(args.import_ths)
    
    if args.ths_members:
        collect_ths_members(pro, refresh=args.refresh)
    
    if args.ths_daily:
        collect_ths_daily(pro, args.start_date, args.end_date, refresh=args.refresh)

if __name__ == '__main__':
    main()
