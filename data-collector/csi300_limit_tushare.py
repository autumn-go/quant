"""
沪深300涨跌停数据采集（使用tushare）
"""

import tushare as ts
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import time

TOKEN = '75d5fb0d2da34ab076f1ab49eaecfac348aaf91faf06246bfcab9f68904c'
DB_PATH = 'csi300_data.db'
START_DATE = '20250101'
RATE_LIMIT = 0.05


def init_tushare():
    ts.set_token(TOKEN)
    pro = ts.pro_api(TOKEN)
    pro._DataApi__token = TOKEN
    pro._DataApi__http_url = 'http://lianghua.nanyangqiankun.top'
    return pro


def get_trade_dates(pro, start_date, end_date):
    """获取交易日历"""
    try:
        trade_cal = pro.trade_cal(exchange='SSE', start_date=start_date, end_date=end_date)
        trade_dates = trade_cal[trade_cal['is_open'] == 1]['cal_date'].tolist()
        return trade_dates
    except Exception as e:
        print(f"获取交易日历失败: {e}")
        return []


def main():
    pro = init_tushare()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    end_date = datetime.now().strftime('%Y%m%d')
    
    print(f"[4/4] 使用tushare采集涨跌停数据 ({START_DATE} - {end_date})...")
    
    # 获取交易日历
    trade_dates = get_trade_dates(pro, START_DATE, end_date)
    print(f"  共 {len(trade_dates)} 个交易日")
    
    # 检查已完成的日期
    cursor.execute('SELECT DISTINCT date FROM limit_up_down')
    completed_dates = set(row[0] for row in cursor.fetchall())
    
    to_collect = [d for d in trade_dates if d not in completed_dates]
    print(f"  跳过已完成: {len(completed_dates)} 天, 待采集: {len(to_collect)} 天")
    
    success = 0
    total_records = 0
    start_time = time.time()
    
    for i, trade_date in enumerate(to_collect):
        try:
            # 采集涨跌停数据
            df = pro.limit_list(trade_date=trade_date)
            
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    try:
                        cursor.execute('''
                            INSERT OR REPLACE INTO limit_up_down 
                            (date, code, name, close, pct_change, turnover_rate, limit_type, amount, industry)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            trade_date,
                            str(row.get('ts_code', '')),
                            str(row.get('name', '')),
                            float(row.get('close', 0) or 0),
                            float(row.get('pct_chg', 0) or 0),
                            float(row.get('turnover_ratio', 0) or 0),
                            str(row.get('limit_type', '')),  # U=涨停, D=跌停
                            float(row.get('amount', 0) or 0),
                            ''  # tushare没有直接提供行业字段
                        ))
                    except Exception as e:
                        pass
                
                conn.commit()
                success += 1
                total_records += len(df)
            
            # 进度显示
            if (i + 1) % 10 == 0 or i == len(to_collect) - 1:
                elapsed = time.time() - start_time
                print(f"  [{i+1}/{len(to_collect)}] 成功:{success} 记录:{total_records} 用时:{elapsed/60:.1f}分")
            
            time.sleep(RATE_LIMIT)
            
        except Exception as e:
            if (i + 1) % 10 == 0:
                print(f"  [WARN] {trade_date} 失败: {e}")
            time.sleep(0.2)
    
    elapsed = time.time() - start_time
    print(f"\n  ✓ 完成! 成功:{success} 天, 共 {total_records} 条记录, 用时:{elapsed/60:.1f}分")
    
    # 统计
    cursor.execute('SELECT limit_type, COUNT(*) FROM limit_up_down GROUP BY limit_type')
    print("\n  数据分布:")
    for row in cursor.fetchall():
        print(f"    {row[0]}: {row[1]} 条")
    
    conn.close()


if __name__ == "__main__":
    main()
