"""
沪深300涨跌停数据采集（只采集最近30天涨停数据）
"""

import akshare as ak
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import time

DB_PATH = 'csi300_data.db'


def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 只采集最近30天
    end_date = datetime.now()
    start_date = end_date - timedelta(days=45)  # 多取一些，确保覆盖30个交易日
    
    date_range = pd.date_range(start=start_date, end=end_date, freq='B')
    dates = [d.strftime('%Y%m%d') for d in date_range]
    
    print(f"[4/4] 采集最近30天涨停数据...")
    print(f"  共 {len(dates)} 个交易日")
    
    success_count = 0
    total_records = 0
    start_time = time.time()
    
    for i, date in enumerate(dates, 1):
        try:
            # 只采集涨停数据
            df = ak.stock_zt_pool_em(date=date)
            
            if df is not None and not df.empty:
                df['limit_type'] = 'up'
                
                for _, row in df.iterrows():
                    try:
                        cursor.execute('''
                            INSERT OR REPLACE INTO limit_up_down 
                            (date, code, name, close, pct_change, turnover_rate, limit_type, amount, industry)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (date, 
                              str(row.get('代码', '')), 
                              str(row.get('名称', '')),
                              float(row.get('最新价', 0) or 0), 
                              float(row.get('涨跌幅', 0) or 0),
                              float(row.get('换手率', 0) or 0), 
                              'up',
                              float(row.get('成交额', 0) or 0), 
                              str(row.get('所属行业', ''))))
                    except:
                        pass
                
                conn.commit()
                success_count += 1
                total_records += len(df)
            
            # 进度显示
            if i % 5 == 0 or i == len(dates):
                elapsed = time.time() - start_time
                print(f"  [{i}/{len(dates)}] 成功:{success_count} 记录:{total_records} 用时:{elapsed/60:.1f}分")
            
            time.sleep(0.3)
            
        except Exception as e:
            print(f"  [WARN] {date} 失败: {e}")
            time.sleep(0.5)
    
    elapsed = time.time() - start_time
    print(f"  ✓ 完成! 成功:{success_count} 天, 共 {total_records} 条涨停记录, 用时:{elapsed/60:.1f}分")
    
    conn.close()


if __name__ == "__main__":
    main()
