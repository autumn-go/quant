"""
沪深300涨跌停数据采集（使用tushare kpl_list和limit_list_ths接口）
采集2025年以来：涨停池、连板池、跌停池
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


def collect_kpl_list(pro, trade_date, tag='涨停'):
    """使用kpl_list接口采集开盘啦数据"""
    try:
        df = pro.kpl_list(trade_date=trade_date, tag=tag, 
                         fields='ts_code,name,trade_date,tag,theme,status')
        return df if df is not None and not df.empty else pd.DataFrame()
    except Exception as e:
        print(f"    kpl_list {trade_date} {tag} 失败: {e}")
        return pd.DataFrame()


def collect_limit_list_ths(pro, trade_date, limit_type='涨停池'):
    """使用limit_list_ths接口采集同花顺涨跌停数据"""
    try:
        df = pro.limit_list_ths(trade_date=trade_date, limit_type=limit_type)
        return df if df is not None and not df.empty else pd.DataFrame()
    except Exception as e:
        print(f"    limit_list_ths {trade_date} {limit_type} 失败: {e}")
        return pd.DataFrame()


def save_to_db(conn, cursor, df, source='kpl'):
    """保存数据到数据库"""
    if df.empty:
        return 0
    
    count = 0
    for _, row in df.iterrows():
        try:
            # 确定limit_type
            if source == 'kpl':
                tag = row.get('tag', '')
                if '涨停' in tag:
                    limit_type = 'up'
                elif '跌停' in tag:
                    limit_type = 'down'
                else:
                    limit_type = 'other'
                theme = row.get('theme', '')
                status = row.get('status', '')
            else:  # ths
                limit_type_map = {
                    '涨停池': 'up',
                    '连板池': 'up_streak',
                    '跌停池': 'down',
                    '冲刺涨停': 'up_sprint',
                    '炸板池': 'up_break'
                }
                ths_type = row.get('limit_type', '涨停池')
                limit_type = limit_type_map.get(ths_type, 'up')
                theme = row.get('concept', '')  # 同花顺用concept字段
                status = ''
            
            cursor.execute('''
                INSERT OR REPLACE INTO limit_up_down 
                (date, code, name, close, pct_change, turnover_rate, limit_type, amount, industry, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                str(row.get('trade_date', '')),
                str(row.get('ts_code', '')),
                str(row.get('name', '')),
                float(row.get('close', 0) or 0),
                float(row.get('pct_chg', row.get('pct_change', 0)) or 0),
                float(row.get('turnover_ratio', 0) or 0),
                limit_type,
                float(row.get('amount', 0) or 0),
                str(theme),
                source
            ))
            count += 1
        except Exception as e:
            pass
    
    conn.commit()
    return count


def init_limit_table(conn, cursor):
    """初始化表结构（添加source字段）"""
    try:
        cursor.execute('ALTER TABLE limit_up_down ADD COLUMN source TEXT')
    except:
        pass  # 字段已存在
    
    try:
        cursor.execute('ALTER TABLE limit_up_down ADD COLUMN status TEXT')
    except:
        pass
    
    conn.commit()


def main():
    pro = init_tushare()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 初始化表结构
    init_limit_table(conn, cursor)
    
    end_date = datetime.now().strftime('%Y%m%d')
    
    print(f"[4/4] 使用tushare采集涨跌停数据 ({START_DATE} - {end_date})...")
    
    # 获取交易日历
    trade_dates = get_trade_dates(pro, START_DATE, end_date)
    print(f"  共 {len(trade_dates)} 个交易日")
    
    # 检查已完成的日期（按source区分）
    cursor.execute('SELECT DISTINCT date FROM limit_up_down WHERE source IS NOT NULL')
    completed_dates = set(row[0] for row in cursor.fetchall())
    
    to_collect = [d for d in trade_dates if d not in completed_dates]
    print(f"  跳过已完成: {len(completed_dates)} 天, 待采集: {len(to_collect)} 天")
    
    total_kpl = 0
    total_ths = 0
    start_time = time.time()
    
    for i, trade_date in enumerate(to_collect):
        daily_kpl = 0
        daily_ths = 0
        
        try:
            # 方法1: kpl_list接口 - 采集涨停和跌停
            for tag in ['涨停', '跌停']:
                df = collect_kpl_list(pro, trade_date, tag)
                if not df.empty:
                    count = save_to_db(conn, cursor, df, source='kpl')
                    daily_kpl += count
            
            # 方法2: limit_list_ths接口 - 采集涨停池、连板池、跌停池
            for limit_type in ['涨停池', '连板池', '跌停池']:
                df = collect_limit_list_ths(pro, trade_date, limit_type)
                if not df.empty:
                    count = save_to_db(conn, cursor, df, source='ths')
                    daily_ths += count
            
            total_kpl += daily_kpl
            total_ths += daily_ths
            
            # 进度显示
            if (i + 1) % 10 == 0 or i == len(to_collect) - 1:
                elapsed = time.time() - start_time
                print(f"  [{i+1}/{len(to_collect)}] kpl:{total_kpl} ths:{total_ths} 用时:{elapsed/60:.1f}分")
            
            time.sleep(RATE_LIMIT)
            
        except Exception as e:
            if (i + 1) % 10 == 0:
                print(f"  [WARN] {trade_date} 失败: {e}")
            time.sleep(0.2)
    
    elapsed = time.time() - start_time
    print(f"\n  ✓ 完成! kpl:{total_kpl}条, ths:{total_ths}条, 用时:{elapsed/60:.1f}分")
    
    # 统计
    print("\n  数据分布:")
    cursor.execute('SELECT source, limit_type, COUNT(*) FROM limit_up_down WHERE source IS NOT NULL GROUP BY source, limit_type')
    for row in cursor.fetchall():
        print(f"    {row[0]} - {row[1]}: {row[2]} 条")
    
    conn.close()


if __name__ == "__main__":
    main()
