#!/usr/bin/env python3
"""
同花顺一级行业日行情数据采集器
- 采集2026年以来89个一级行业的日K数据
- 使用Tushare Pro的ths_daily接口
"""

import tushare as ts
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import time
import os
import sys
from typing import Optional
from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stderr, level="INFO")
logger.add("logs/industry_daily.log", rotation="50 MB", level="DEBUG")

# Tushare Token
TOKEN = '75d5fb0d2da34ab076f1ab49eaecfac348aaf91faf06246bfcab9f68904c'
DB_PATH = "quant_data_2026.db"
START_DATE = '20260101'
RATE_LIMIT = 0.2  # 行业数据请求间隔稍长


class IndustryDataCollector:
    def __init__(self, token: str = TOKEN, db_path: str = DB_PATH):
        self.token = token
        self.db_path = db_path
        
        # 初始化 Tushare
        ts.set_token(token)
        self.pro = ts.pro_api(token)
        self.pro._DataApi__token = token
        self.pro._DataApi__http_url = 'http://lianghua.nanyangqiankun.top'
        
        logger.info(f"IndustryDataCollector initialized, DB: {db_path}")
    
    def get_industry_list(self) -> list:
        """获取行业列表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute('SELECT ts_code FROM ths_industries ORDER BY ts_code')
        industries = [row[0] for row in cursor.fetchall()]
        conn.close()
        return industries
    
    def get_last_update_date(self, ts_code: str) -> Optional[str]:
        """获取行业最后更新日期"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute('SELECT last_date FROM industry_progress WHERE ts_code = ?', (ts_code,))
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0]:
            return result[0]
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute('SELECT MAX(trade_date) FROM industry_daily WHERE ts_code = ?', (ts_code,))
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result and result[0] else None
    
    def fetch_industry_daily(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取行业日线数据"""
        try:
            # 使用ths_daily接口获取同花顺行业数据，包含总市值和流通市值
            df = self.pro.ths_daily(
                ts_code=ts_code, 
                start_date=start_date, 
                end_date=end_date,
                fields='ts_code,trade_date,open,high,low,close,pre_close,avg_price,change,pct_change,vol,turnover_rate,total_mv,float_mv'
            )
            
            if df is None or df.empty:
                return pd.DataFrame()
            
            return df
            
        except Exception as e:
            logger.error(f"Failed to fetch {ts_code}: {e}")
            return pd.DataFrame()
    
    def save_daily_data(self, df: pd.DataFrame) -> int:
        """保存日线数据"""
        if df.empty:
            return 0
        
        conn = sqlite3.connect(self.db_path)
        count = 0
        
        for _, row in df.iterrows():
            try:
                conn.execute('''INSERT OR REPLACE INTO industry_daily 
                    (ts_code, trade_date, open, high, low, close, pre_close, avg_price, 
                     change, pct_change, volume, turnover_rate, total_mv, float_mv)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (row['ts_code'], row['trade_date'], row['open'], row['high'],
                     row['low'], row['close'], row.get('pre_close'), row.get('avg_price'),
                     row.get('change'), row.get('pct_change'), row.get('vol'), 
                     row.get('turnover_rate'), row.get('total_mv'), row.get('float_mv'))
                )
                count += 1
            except Exception as e:
                logger.error(f"Failed to save {row['ts_code']} {row['trade_date']}: {e}")
        
        conn.commit()
        conn.close()
        return count
    
    def update_progress(self, ts_code: str, last_date: str, status: str = 'completed'):
        """更新采集进度"""
        conn = sqlite3.connect(self.db_path)
        conn.execute('''INSERT OR REPLACE INTO industry_progress 
            (ts_code, last_date, status, updated_at)
            VALUES (?, ?, ?, ?)''',
            (ts_code, last_date, status, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
    
    def collect_industry(self, ts_code: str) -> dict:
        """采集单个行业数据"""
        try:
            # 确定日期范围
            last_date = self.get_last_update_date(ts_code)
            
            if last_date:
                start = (datetime.strptime(last_date, '%Y%m%d') + timedelta(days=1)).strftime('%Y%m%d')
            else:
                start = START_DATE
            
            end = datetime.now().strftime('%Y%m%d')
            
            if start > end:
                return {'ts_code': ts_code, 'status': 'skipped', 'count': 0, 'message': 'Already up to date'}
            
            # 采集数据
            df = self.fetch_industry_daily(ts_code, start, end)
            
            if df.empty:
                return {'ts_code': ts_code, 'status': 'empty', 'count': 0, 'message': 'No data'}
            
            # 保存数据
            count = self.save_daily_data(df)
            
            # 更新进度
            last_data_date = df['trade_date'].max()
            self.update_progress(ts_code, last_data_date, 'completed')
            
            time.sleep(RATE_LIMIT)
            
            return {
                'ts_code': ts_code,
                'status': 'success',
                'count': count,
                'start': start,
                'end': end
            }
            
        except Exception as e:
            logger.error(f"Failed to collect {ts_code}: {e}")
            self.update_progress(ts_code, '', f'error: {str(e)}')
            return {'ts_code': ts_code, 'status': 'error', 'count': 0, 'message': str(e)}
    
    def collect_all(self):
        """采集所有行业数据"""
        industries = self.get_industry_list()
        logger.info(f"Starting to collect {len(industries)} industries...")
        
        # 获取已完成的
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT ts_code FROM industry_progress WHERE status = 'completed'")
        completed = set(row[0] for row in cursor.fetchall())
        conn.close()
        
        industries_to_collect = [c for c in industries if c not in completed]
        logger.info(f"Skipped {len(industries) - len(industries_to_collect)} already completed")
        
        results = []
        start_time = time.time()
        
        for i, ts_code in enumerate(industries_to_collect):
            result = self.collect_industry(ts_code)
            results.append(result)
            
            if (i + 1) % 10 == 0 or i == len(industries_to_collect) - 1:
                elapsed = (time.time() - start_time) / 60
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                progress_pct = (i + 1) / len(industries_to_collect) * 100
                logger.info(f"[{i+1}/{len(industries_to_collect)}] {ts_code}: {result['status']}, "
                           f"已用 {elapsed:.1f} 分, 速度 {rate:.1f} 个/分, 进度 {progress_pct:.1f}%")
        
        # 统计
        success = sum(1 for r in results if r['status'] == 'success')
        skipped = sum(1 for r in results if r['status'] == 'skipped')
        empty = sum(1 for r in results if r['status'] == 'empty')
        error = sum(1 for r in results if r['status'] == 'error')
        total_records = sum(r.get('count', 0) for r in results)
        
        logger.info("=" * 60)
        logger.info(f"行业数据采集完成!")
        logger.info(f"成功: {success}, 跳过: {skipped}, 空数据: {empty}, 错误: {error}")
        logger.info(f"总记录数: {total_records}")
        logger.info(f"总用时: {(time.time() - start_time)/60:.1f} 分钟")
        logger.info("=" * 60)
        
        return results
    
    def get_stats(self) -> dict:
        """获取统计"""
        conn = sqlite3.connect(self.db_path)
        
        cursor = conn.execute('SELECT COUNT(*) FROM ths_industries')
        total = cursor.fetchone()[0]
        
        cursor = conn.execute('SELECT COUNT(*) FROM industry_daily')
        daily_count = cursor.fetchone()[0]
        
        cursor = conn.execute('SELECT COUNT(DISTINCT ts_code) FROM industry_daily')
        with_data = cursor.fetchone()[0]
        
        cursor = conn.execute('SELECT MIN(trade_date), MAX(trade_date) FROM industry_daily')
        date_range = cursor.fetchone()
        
        conn.close()
        
        return {
            'total_industries': total,
            'daily_records': daily_count,
            'industries_with_data': with_data,
            'date_range': date_range
        }


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='同花顺一级行业日行情采集')
    parser.add_argument('--full', action='store_true', help='全量采集')
    parser.add_argument('--update', action='store_true', help='增量更新')
    parser.add_argument('--stats', action='store_true', help='查看统计')
    parser.add_argument('--code', type=str, help='指定行业代码')
    
    args = parser.parse_args()
    
    os.makedirs('logs', exist_ok=True)
    
    collector = IndustryDataCollector()
    
    if args.full or args.update:
        mode = "全量" if args.full else "增量"
        logger.info(f"Starting {mode} industry data collection...")
        collector.collect_all()
    
    elif args.code:
        result = collector.collect_industry(args.code)
        logger.info(f"Result: {result}")
    
    elif args.stats:
        stats = collector.get_stats()
        print("\n" + "=" * 60)
        print("同花顺一级行业统计")
        print("=" * 60)
        print(f"行业总数: {stats['total_industries']}")
        print(f"日线记录: {stats['daily_records']}")
        print(f"有数据行业: {stats['industries_with_data']}")
        if stats['date_range'] and stats['date_range'][0]:
            print(f"数据范围: {stats['date_range'][0]} ~ {stats['date_range'][1]}")
        print("=" * 60)
    
    else:
        parser.print_help()
        print("\n示例:")
        print("  python3 industry_daily_collector.py --full      # 全量采集")
        print("  python3 industry_daily_collector.py --update    # 增量更新")
        print("  python3 industry_daily_collector.py --stats     # 查看统计")


if __name__ == '__main__':
    main()
