#!/usr/bin/env python3
"""
增量补充2024年剩余涨跌停数据
"""

import tushare as ts
import sqlite3
import pandas as pd
from datetime import datetime
import time

TOKEN = '75d5fb0d2da34ab076f1ab49eaecfac348aaf91faf06246bfcab9f68904c'
DB_PATH = 'csi300_data.db'

def init_tushare():
    ts.set_token(TOKEN)
    pro = ts.pro_api(TOKEN)
    pro._DataApi__token = TOKEN
    pro._DataApi__http_url = 'http://lianghua.nanyangqiankun.top'
    return pro

def main():
    pro = init_tushare()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("检查2024年缺失的交易日...")
    
    # 获取已采集的2024年日期
    cursor.execute("SELECT DISTINCT date FROM limit_up_down WHERE date LIKE '2024%'")
    existing_dates = set(row[0] for row in cursor.fetchall())
    
    # 生成2024年所有工作日
    all_dates = pd.date_range(start='20240101', end='20241231', freq='B')
    all_dates = [d.strftime('%Y%m%d') for d in all_dates]
    
    # 找出缺失的日期
    missing_dates = [d for d in all_dates if d not in existing_dates]
    
    print(f"已采集: {len(existing_dates)} 天")
    print(f"待补充: {len(missing_dates)} 天")
    print("="*60)
    
    if len(missing_dates) == 0:
        print("2024年数据已完整!")
        return
    
    print(f"\n开始采集剩余 {len(missing_dates)} 天...")
    
    total_added = 0
    for i, date in enumerate(missing_dates):
        try:
            # kpl_list - 涨停
            df_up = pro.kpl_list(trade_date=date, tag='涨停', fields='ts_code,name,trade_date,tag,theme,status')
            if df_up is not None and not df_up.empty:
                for _, row in df_up.iterrows():
                    cursor.execute('''
                        INSERT INTO limit_up_down (date, code, name, pct_change, limit_type, industry, source, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (date, row['ts_code'], row['name'], 0, 'up', row.get('theme', ''), 'kpl', row.get('status', '')))
                total_added += len(df_up)
            
            # kpl_list - 跌停
            df_down = pro.kpl_list(trade_date=date, tag='跌停', fields='ts_code,name,trade_date,tag,theme,status')
            if df_down is not None and not df_down.empty:
                for _, row in df_down.iterrows():
                    cursor.execute('''
                        INSERT INTO limit_up_down (date, code, name, pct_change, limit_type, industry, source, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (date, row['ts_code'], row['name'], 0, 'down', row.get('theme', ''), 'kpl', row.get('status', '')))
                total_added += len(df_down)
            
            conn.commit()
            
            if (i + 1) % 20 == 0:
                print(f"  进度: {i+1}/{len(missing_dates)} 天, 新增 {total_added} 条")
            
            time.sleep(0.05)
        except Exception as e:
            pass
    
    print(f"\n完成! 新增 {total_added} 条记录")
    
    # 统计
    cursor.execute("SELECT COUNT(DISTINCT date) FROM limit_up_down WHERE date LIKE '2024%'")
    days_2024 = cursor.fetchone()[0]
    print(f"2024年现在共有 {days_2024} 个交易日数据")
    
    conn.close()

if __name__ == "__main__":
    main()
