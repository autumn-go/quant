"""
沪深300涨跌停数据采集（补充脚本）
"""

import akshare as ak
import pandas as pd
import sqlite3
from datetime import datetime
import time

DB_PATH = 'csi300_data.db'
START_DATE = '20250101'
END_DATE = datetime.now().strftime('%Y%m%d')


def fetch_limit_up_down(date: str) -> pd.DataFrame:
    """采集指定日期的涨跌停数据"""
    try:
        # 涨停数据
        df_up = ak.stock_zt_pool_em(date=date)
        if df_up is not None and not df_up.empty:
            df_up['limit_type'] = 'up'
        else:
            df_up = pd.DataFrame()
        
        # 跌停数据
        df_down = ak.stock_zt_pool_dtgc_em(date=date)
        if df_down is not None and not df_down.empty:
            df_down['limit_type'] = 'down'
        else:
            df_down = pd.DataFrame()
        
        # 合并
        if not df_up.empty and not df_down.empty:
            df = pd.concat([df_up, df_down], ignore_index=True)
        elif not df_up.empty:
            df = df_up
        elif not df_down.empty:
            df = df_down
        else:
            df = pd.DataFrame()
        
        return df
    except Exception as e:
        print(f"    {date} 采集失败: {e}")
        return pd.DataFrame()


def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 生成交易日列表（工作日）
    date_range = pd.date_range(start=START_DATE, end=END_DATE, freq='B')
    dates = [d.strftime('%Y%m%d') for d in date_range]
    
    print(f"[4/4] 采集涨跌停数据 ({START_DATE} - {END_DATE})...")
    print(f"  共 {len(dates)} 个交易日需要采集")
    
    success_count = 0
    total_records = 0
    start_time = time.time()
    
    for i, date in enumerate(dates, 1):
        try:
            # 检查是否已采集
            cursor.execute('SELECT COUNT(*) FROM limit_up_down WHERE date = ?', (date,))
            if cursor.fetchone()[0] > 0:
                continue
            
            df = fetch_limit_up_down(date)
            
            if not df.empty:
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
                              str(row.get('limit_type', '')),
                              float(row.get('成交额', 0) or 0), 
                              str(row.get('所属行业', ''))))
                    except Exception as e:
                        pass
                
                conn.commit()
                success_count += 1
                total_records += len(df)
            
            # 进度显示
            if i % 5 == 0 or i == len(dates):
                elapsed = time.time() - start_time
                print(f"  [{i}/{len(dates)}] 成功:{success_count} 记录:{total_records} 用时:{elapsed/60:.1f}分")
            
            time.sleep(0.3)  # 限速
            
        except Exception as e:
            if i % 5 == 0:
                print(f"  [WARN] {date} 失败: {e}")
            time.sleep(0.5)
    
    elapsed = time.time() - start_time
    print(f"  ✓ 完成! 成功:{success_count} 天, 共 {total_records} 条记录, 用时:{elapsed/60:.1f}分")
    
    conn.close()


if __name__ == "__main__":
    main()
