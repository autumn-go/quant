#!/usr/bin/env python3
"""
简化版涨跌停数据采集
"""

import tushare as ts
import sqlite3
import pandas as pd
from datetime import datetime
import time

TOKEN = '75d5fb0d2da34ab076f1ab49eaecfac348aaf91faf06246bfcab9f68904c'
DB_PATH = 'csi300_data.db'

# 初始化tushare
ts.set_token(TOKEN)
pro = ts.pro_api(TOKEN)
pro._DataApi__token = TOKEN
pro._DataApi__http_url = 'http://lianghua.nanyangqiankun.top'

# 连接数据库
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 添加新字段
try:
    cursor.execute('ALTER TABLE limit_up_down ADD COLUMN source TEXT')
except:
    pass
try:
    cursor.execute('ALTER TABLE limit_up_down ADD COLUMN status TEXT')
except:
    pass
conn.commit()

# 清空旧数据
cursor.execute('DELETE FROM limit_up_down')
conn.commit()
print("已清空旧数据")

# 生成交易日列表
start_date = '20250101'
end_date = datetime.now().strftime('%Y%m%d')
dates = pd.date_range(start=start_date, end=end_date, freq='B')
dates = [d.strftime('%Y%m%d') for d in dates]

print(f"开始采集 {len(dates)} 个交易日的数据...")
print("="*60)

total_records = 0
start_time = time.time()

for i, date in enumerate(dates):
    daily_count = 0
    
    # 1. kpl_list - 涨停
    try:
        df = pro.kpl_list(trade_date=date, tag='涨停', fields='ts_code,name,trade_date,tag,theme,status')
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                cursor.execute('''
                    INSERT INTO limit_up_down (date, code, name, pct_change, limit_type, industry, source, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (date, row['ts_code'], row['name'], 0, 'up', row.get('theme', ''), 'kpl', row.get('status', '')))
            daily_count += len(df)
    except:
        pass
    
    # 2. kpl_list - 跌停
    try:
        df = pro.kpl_list(trade_date=date, tag='跌停', fields='ts_code,name,trade_date,tag,theme,status')
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                cursor.execute('''
                    INSERT INTO limit_up_down (date, code, name, pct_change, limit_type, industry, source, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (date, row['ts_code'], row['name'], 0, 'down', row.get('theme', ''), 'kpl', row.get('status', '')))
            daily_count += len(df)
    except:
        pass
    
    # 3. limit_list_ths - 涨停池
    try:
        df = pro.limit_list_ths(trade_date=date, limit_type='涨停池')
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                cursor.execute('''
                    INSERT INTO limit_up_down (date, code, name, close, pct_change, turnover_rate, limit_type, amount, industry, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (date, row['ts_code'], row['name'], row.get('close', 0), row.get('pct_chg', 0),
                      row.get('turnover_ratio', 0), 'up', row.get('amount', 0), row.get('concept', ''), 'ths'))
            daily_count += len(df)
    except:
        pass
    
    # 4. limit_list_ths - 连板池
    try:
        df = pro.limit_list_ths(trade_date=date, limit_type='连板池')
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                cursor.execute('''
                    INSERT INTO limit_up_down (date, code, name, close, pct_change, turnover_rate, limit_type, amount, industry, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (date, row['ts_code'], row['name'], row.get('close', 0), row.get('pct_chg', 0),
                      row.get('turnover_ratio', 0), 'up_streak', row.get('amount', 0), row.get('concept', ''), 'ths'))
            daily_count += len(df)
    except:
        pass
    
    # 5. limit_list_ths - 跌停池
    try:
        df = pro.limit_list_ths(trade_date=date, limit_type='跌停池')
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                cursor.execute('''
                    INSERT INTO limit_up_down (date, code, name, close, pct_change, turnover_rate, limit_type, amount, industry, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (date, row['ts_code'], row['name'], row.get('close', 0), row.get('pct_chg', 0),
                      row.get('turnover_ratio', 0), 'down', row.get('amount', 0), row.get('concept', ''), 'ths'))
            daily_count += len(df)
    except:
        pass
    
    conn.commit()
    total_records += daily_count
    
    if (i + 1) % 10 == 0 or i == len(dates) - 1:
        elapsed = time.time() - start_time
        print(f"[{i+1}/{len(dates)}] {date} 当天{daily_count}条 累计{total_records}条 用时{elapsed/60:.1f}分")
    
    time.sleep(0.05)

elapsed = time.time() - start_time
print("="*60)
print(f"完成! 共 {total_records} 条记录, 用时 {elapsed/60:.1f} 分钟")

# 统计
cursor.execute('SELECT source, limit_type, COUNT(*) FROM limit_up_down GROUP BY source, limit_type')
print("\n数据分布:")
for row in cursor.fetchall():
    print(f"  {row[0]} - {row[1]}: {row[2]} 条")

cursor.execute('SELECT COUNT(DISTINCT date) FROM limit_up_down')
days = cursor.fetchone()[0]
print(f"\n覆盖交易日: {days} 天")

conn.close()
