#!/usr/bin/env python3
"""
量化数据完整采集器
目标：采集2024年以来所有需要的量化数据
"""

import tushare as ts
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import time
import os
import sys
from loguru import logger

# 配置
TOKEN = '75d5fb0d2da34ab076f1ab49eaecfac348aaf91faf06246bfcab9f68904c'
DB_PATH = "quant_data_2024.db"
START_DATE = '20240101'
RATE_LIMIT = 0.05

class QuantDataCollector:
    def __init__(self):
        ts.set_token(TOKEN)
        self.pro = ts.pro_api(TOKEN)
        self.pro._DataApi__token = TOKEN
        self.pro._DataApi__http_url = 'http://lianghua.nanyangqiankun.top'
        self.init_db()
        logger.info(f"Initialized, DB: {DB_PATH}")
    
    def init_db(self):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # 股票列表
        c.execute('''CREATE TABLE IF NOT EXISTS stocks (
            ts_code TEXT PRIMARY KEY, symbol TEXT, name TEXT, industry TEXT,
            market TEXT, exchange TEXT, list_date TEXT
        )''')
        
        # 指数列表
        c.execute('''CREATE TABLE IF NOT EXISTS index_list (
            ts_code TEXT PRIMARY KEY, name TEXT, market TEXT
        )''')
        
        # 股票日K
        c.execute('''CREATE TABLE IF NOT EXISTS stock_daily (
            ts_code TEXT, trade_date TEXT, open REAL, high REAL, low REAL, close REAL,
            pre_close REAL, change REAL, pct_chg REAL, vol REAL, amount REAL,
            PRIMARY KEY (ts_code, trade_date)
        )''')
        
        # 指数日K
        c.execute('''CREATE TABLE IF NOT EXISTS index_daily (
            ts_code TEXT, trade_date TEXT, open REAL, high REAL, low REAL, close REAL,
            pre_close REAL, change REAL, pct_chg REAL, vol REAL, amount REAL,
            PRIMARY KEY (ts_code, trade_date)
        )''')
        
        # 同花顺行业
        c.execute('''CREATE TABLE IF NOT EXISTS ths_industry (
            code TEXT PRIMARY KEY, name TEXT
        )''')
        
        # 同花顺行业成分
        c.execute('''CREATE TABLE IF NOT EXISTS ths_industry_member (
            industry_code TEXT, ts_code TEXT, name TEXT, in_date TEXT,
            PRIMARY KEY (industry_code, ts_code)
        )''')
        
        # 同花顺概念
        c.execute('''CREATE TABLE IF NOT EXISTS ths_concept (
            code TEXT PRIMARY KEY, name TEXT
        )''')
        
        # 同花顺概念成分
        c.execute('''CREATE TABLE IF NOT EXISTS ths_concept_member (
            concept_code TEXT, ts_code TEXT, name TEXT, in_date TEXT,
            PRIMARY KEY (concept_code, ts_code)
        )''')
        
        # 涨跌停数据
        c.execute('''CREATE TABLE IF NOT EXISTS limit_up_down (
            trade_date TEXT, ts_code TEXT, name TEXT, close REAL, pct_chg REAL,
            limit_type TEXT, open_times INTEGER, fd_amount REAL,
            PRIMARY KEY (trade_date, ts_code)
        )''')
        
        # 连板天梯
        c.execute('''CREATE TABLE IF NOT EXISTS limit_up_streak (
            trade_date TEXT, ts_code TEXT, name TEXT, close REAL, pct_chg REAL,
            consecutive_boards INTEGER, turnover_ratio REAL,
            PRIMARY KEY (trade_date, ts_code)
        )''')
        
        # 进度表
        c.execute('''CREATE TABLE IF NOT EXISTS collection_progress (
            task_name TEXT PRIMARY KEY, last_date TEXT, status TEXT
        )''')
        
        conn.commit()
        conn.close()
    
    def save_progress(self, task_name, last_date, status='completed'):
        conn = sqlite3.connect(DB_PATH)
        conn.execute('''INSERT OR REPLACE INTO collection_progress VALUES (?,?,?)''',
            (task_name, last_date, status))
        conn.commit()
        conn.close()
    
    def get_progress(self, task_name):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.execute('SELECT last_date, status FROM collection_progress WHERE task_name = ?', (task_name,))
        row = cursor.fetchone()
        conn.close()
        return row if row else (None, None)
    
    def collect_stock_list(self):
        """采集A股列表"""
        logger.info("[1/8] 采集A股列表...")
        df = self.pro.stock_basic(exchange='', list_status='L')
        
        conn = sqlite3.connect(DB_PATH)
        for _, row in df.iterrows():
            conn.execute('''INSERT OR REPLACE INTO stocks VALUES (?,?,?,?,?,?,?)''',
                (row['ts_code'], row['symbol'], row['name'], row.get('industry'),
                 row.get('market'), row.get('exchange'), row.get('list_date')))
        conn.commit()
        conn.close()
        
        self.save_progress('stock_list', datetime.now().strftime('%Y%m%d'))
        logger.info(f"[1/8] A股列表完成: {len(df)} 只")
        return df['ts_code'].tolist()
    
    def collect_index_list(self):
        """采集指数列表"""
        logger.info("[2/8] 采集指数列表...")
        
        all_indices = []
        for market in ['SSE', 'SZSE', 'CSI']:
            try:
                df = self.pro.index_basic(market=market)
                if df is not None and not df.empty:
                    all_indices.append(df[['ts_code', 'name', 'market']])
                time.sleep(RATE_LIMIT)
            except Exception as e:
                logger.warning(f"获取 {market} 指数失败: {e}")
        
        if all_indices:
            df = pd.concat(all_indices, ignore_index=True)
            conn = sqlite3.connect(DB_PATH)
            for _, row in df.iterrows():
                conn.execute('''INSERT OR REPLACE INTO index_list VALUES (?,?,?)''',
                    (row['ts_code'], row['name'], row['market']))
            conn.commit()
            conn.close()
            
            self.save_progress('index_list', datetime.now().strftime('%Y%m%d'))
            logger.info(f"[2/8] 指数列表完成: {len(df)} 个")
            return df['ts_code'].tolist()
        return []
    
    def collect_stock_daily(self, stock_codes):
        """采集A股日K数据"""
        logger.info(f"[3/8] 采集A股日K数据: {len(stock_codes)} 只...")
        
        # 检查已完成的
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.execute('SELECT ts_code FROM stock_daily WHERE trade_date >= ? GROUP BY ts_code', (START_DATE,))
        completed = set(row[0] for row in cursor.fetchall())
        conn.close()
        
        to_collect = [c for c in stock_codes if c not in completed]
        logger.info(f"跳过已完成: {len(completed)}, 待采集: {len(to_collect)}")
        
        end_date = datetime.now().strftime('%Y%m%d')
        success = 0
        
        conn = sqlite3.connect(DB_PATH)
        for i, ts_code in enumerate(to_collect):
            try:
                df = self.pro.daily(ts_code=ts_code, start_date=START_DATE, end_date=end_date)
                if df is not None and not df.empty:
                    for _, row in df.iterrows():
                        conn.execute('''INSERT OR REPLACE INTO stock_daily 
                            VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                            (row['ts_code'], row['trade_date'], row['open'], row['high'],
                             row['low'], row['close'], row['pre_close'], row['change'],
                             row['pct_chg'], row['vol'], row['amount']))
                    conn.commit()
                    success += 1
                
                if (i + 1) % 100 == 0:
                    logger.info(f"  进度: {i+1}/{len(to_collect)}, 成功: {success}")
                
                time.sleep(RATE_LIMIT)
            except Exception as e:
                logger.error(f"{ts_code} 失败: {e}")
        
        conn.close()
        self.save_progress('stock_daily', end_date)
        logger.info(f"[3/8] A股日K完成: 成功 {success}/{len(to_collect)}")
    
    def collect_index_daily(self, index_codes):
        """采集指数日K数据"""
        logger.info(f"[4/8] 采集指数日K数据: {len(index_codes)} 个...")
        
        end_date = datetime.now().strftime('%Y%m%d')
        success = 0
        
        conn = sqlite3.connect(DB_PATH)
        for i, ts_code in enumerate(index_codes):
            try:
                df = self.pro.index_daily(ts_code=ts_code, start_date=START_DATE, end_date=end_date)
                if df is not None and not df.empty:
                    for _, row in df.iterrows():
                        conn.execute('''INSERT OR REPLACE INTO index_daily 
                            VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                            (row['ts_code'], row['trade_date'], row['open'], row['high'],
                             row['low'], row['close'], row['pre_close'], row['change'],
                             row['pct_chg'], row['vol'], row['amount']))
                    conn.commit()
                    success += 1
                
                if (i + 1) % 50 == 0:
                    logger.info(f"  进度: {i+1}/{len(index_codes)}, 成功: {success}")
                
                time.sleep(RATE_LIMIT)
            except Exception as e:
                logger.error(f"{ts_code} 失败: {e}")
        
        conn.close()
        self.save_progress('index_daily', end_date)
        logger.info(f"[4/8] 指数日K完成: 成功 {success}/{len(index_codes)}")
    
    def collect_ths_industry(self):
        """采集同花顺行业板块"""
        logger.info("[5/8] 采集同花顺行业板块...")
        
        try:
            # 获取行业列表
            df = self.pro.ths_index(type='I')
            if df is None or df.empty:
                logger.warning("同花顺行业列表为空")
                return []
            
            conn = sqlite3.connect(DB_PATH)
            industry_codes = []
            
            for _, row in df.iterrows():
                code = row['ts_code']
                industry_codes.append(code)
                conn.execute('''INSERT OR REPLACE INTO ths_industry VALUES (?,?)''',
                    (code, row['name']))
            conn.commit()
            
            # 获取行业成分股
            logger.info(f"[5/8] 采集行业成分股: {len(industry_codes)} 个行业...")
            for i, code in enumerate(industry_codes):
                try:
                    members = self.pro.ths_member(ts_code=code)
                    if members is not None and not members.empty:
                        for _, m in members.iterrows():
                            conn.execute('''INSERT OR REPLACE INTO ths_industry_member 
                                VALUES (?,?,?,?)''',
                                (code, m['ts_code'], m['name'], m.get('in_date')))
                        conn.commit()
                    
                    if (i + 1) % 10 == 0:
                        logger.info(f"  行业进度: {i+1}/{len(industry_codes)}")
                    
                    time.sleep(RATE_LIMIT)
                except Exception as e:
                    logger.error(f"行业 {code} 成分获取失败: {e}")
            
            conn.close()
            self.save_progress('ths_industry', datetime.now().strftime('%Y%m%d'))
            logger.info(f"[5/8] 同花顺行业完成: {len(industry_codes)} 个行业")
            return industry_codes
            
        except Exception as e:
            logger.error(f"同花顺行业采集失败: {e}")
            return []
    
    def collect_ths_concept(self):
        """采集同花顺概念板块"""
        logger.info("[6/8] 采集同花顺概念板块...")
        
        try:
            # 获取概念列表
            df = self.pro.ths_index(type='N')
            if df is None or df.empty:
                logger.warning("同花顺概念列表为空")
                return []
            
            conn = sqlite3.connect(DB_PATH)
            concept_codes = []
            
            for _, row in df.iterrows():
                code = row['ts_code']
                concept_codes.append(code)
                conn.execute('''INSERT OR REPLACE INTO ths_concept VALUES (?,?)''',
                    (code, row['name']))
            conn.commit()
            
            # 获取概念成分股
            logger.info(f"[6/8] 采集概念成分股: {len(concept_codes)} 个概念...")
            for i, code in enumerate(concept_codes):
                try:
                    members = self.pro.ths_member(ts_code=code)
                    if members is not None and not members.empty:
                        for _, m in members.iterrows():
                            conn.execute('''INSERT OR REPLACE INTO ths_concept_member 
                                VALUES (?,?,?,?)''',
                                (code, m['ts_code'], m['name'], m.get('in_date')))
                        conn.commit()
                    
                    if (i + 1) % 50 == 0:
                        logger.info(f"  概念进度: {i+1}/{len(concept_codes)}")
                    
                    time.sleep(RATE_LIMIT)
                except Exception as e:
                    logger.error(f"概念 {code} 成分获取失败: {e}")
            
            conn.close()
            self.save_progress('ths_concept', datetime.now().strftime('%Y%m%d'))
            logger.info(f"[6/8] 同花顺概念完成: {len(concept_codes)} 个概念")
            return concept_codes
            
        except Exception as e:
            logger.error(f"同花顺概念采集失败: {e}")
            return []
    
    def collect_limit_up_down(self):
        """采集涨跌停数据"""
        logger.info("[7/8] 采集涨跌停数据...")
        
        # 获取交易日历
        try:
            trade_cal = self.pro.trade_cal(exchange='SSE', start_date=START_DATE, 
                                           end_date=datetime.now().strftime('%Y%m%d'))
            trade_dates = trade_cal[trade_cal['is_open'] == 1]['cal_date'].tolist()
        except:
            logger.error("获取交易日历失败")
            return
        
        # 检查已完成的日期
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.execute('SELECT DISTINCT trade_date FROM limit_up_down WHERE trade_date >= ?', (START_DATE,))
        completed_dates = set(row[0] for row in cursor.fetchall())
        conn.close()
        
        to_collect = [d for d in trade_dates if d not in completed_dates]
        logger.info(f"跳过已完成: {len(completed_dates)} 天, 待采集: {len(to_collect)} 天")
        
        conn = sqlite3.connect(DB_PATH)
        success = 0
        
        for i, trade_date in enumerate(to_collect):
            try:
                df = self.pro.limit_list(trade_date=trade_date)
                if df is not None and not df.empty:
                    for _, row in df.iterrows():
                        conn.execute('''INSERT OR REPLACE INTO limit_up_down 
                            VALUES (?,?,?,?,?,?,?,?,?)''',
                            (trade_date, row['ts_code'], row['name'], row['close'],
                             row['pct_chg'], row['limit_type'], row.get('open_times'),
                             row.get('fd_amount')))
                    conn.commit()
                    success += 1
                
                if (i + 1) % 10 == 0:
                    logger.info(f"  日期进度: {i+1}/{len(to_collect)}, 成功: {success}")
                
                time.sleep(RATE_LIMIT)
            except Exception as e:
                logger.error(f"日期 {trade_date} 涨跌停数据获取失败: {e}")
        
        conn.close()
        self.save_progress('limit_up_down', datetime.now().strftime('%Y%m%d'))
        logger.info(f"[7/8] 涨跌停数据完成: {success}/{len(to_collect)} 天")
    
    def collect_limit_up_streak(self):
        """采集连板天梯数据"""
        logger.info("[8/8] 采集连板天梯数据...")
        
        # 获取交易日历
        try:
            trade_cal = self.pro.trade_cal(exchange='SSE', start_date=START_DATE,
                                           end_date=datetime.now().strftime('%Y%m%d'))
            trade_dates = trade_cal[trade_cal['is_open'] == 1]['cal_date'].tolist()
        except:
            logger.error("获取交易日历失败")
            return
        
        # 检查已完成的日期
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.execute('SELECT DISTINCT trade_date FROM limit_up_streak WHERE trade_date >= ?', (START_DATE,))
        completed_dates = set(row[0] for row in cursor.fetchall())
        conn.close()
        
        to_collect = [d for d in trade_dates if d not in completed_dates]
        logger.info(f"跳过已完成: {len(completed_dates)} 天, 待采集: {len(to_collect)} 天")
        
        conn = sqlite3.connect(DB_PATH)
        success = 0
        
        for i, trade_date in enumerate(to_collect):
            try:
                df = self.pro.limit_list(trade_date=trade_date)
                if df is not None and not df.empty:
                    # 筛选连板股票（consecutive_boards > 1）
                    streak_df = df[df['consecutive_boards'] > 0]
                    for _, row in streak_df.iterrows():
                        conn.execute('''INSERT OR REPLACE INTO limit_up_streak 
                            VALUES (?,?,?,?,?,?,?)''',
                            (trade_date, row['ts_code'], row['name'], row['close'],
                             row['pct_chg'], row['consecutive_boards'], row.get('turnover_ratio')))
                    conn.commit()
                    success += 1
                
                if (i + 1) % 10 == 0:
                    logger.info(f"  日期进度: {i+1}/{len(to_collect)}, 成功: {success}")
                
                time.sleep(RATE_LIMIT)
            except Exception as e:
                logger.error(f"日期 {trade_date} 连板数据获取失败: {e}")
        
        conn.close()
        self.save_progress('limit_up_streak', datetime.now().strftime('%Y%m%d'))
        logger.info(f"[8/8] 连板天梯完成: {success}/{len(to_collect)} 天")
    
    def run_all(self):
        """运行完整采集流程"""
        logger.info("=" * 60)
        logger.info("开始完整量化数据采集 (2024年以来)")
        logger.info("=" * 60)
        
        start_time = time.time()
        
        # 1. 股票列表
        stock_codes = self.collect_stock_list()
        
        # 2. 指数列表
        index_codes = self.collect_index_list()
        
        # 3. 股票日K
        if stock_codes:
            self.collect_stock_daily(stock_codes)
        
        # 4. 指数日K
        if index_codes:
            self.collect_index_daily(index_codes)
        
        # 5. 同花顺行业
        self.collect_ths_industry()
        
        # 6. 同花顺概念
        self.collect_ths_concept()
        
        # 7. 涨跌停数据
        self.collect_limit_up_down()
        
        # 8. 连板天梯
        self.collect_limit_up_streak()
        
        elapsed = (time.time() - start_time) / 60
        logger.info("=" * 60)
        logger.info(f"所有任务完成! 总用时: {elapsed:.1f} 分钟")
        logger.info("=" * 60)
    
    def get_stats(self):
        """获取统计信息"""
        conn = sqlite3.connect(DB_PATH)
        stats = {}
        
        tables = ['stocks', 'index_list', 'stock_daily', 'index_daily', 
                  'ths_industry', 'ths_industry_member', 'ths_concept', 'ths_concept_member',
                  'limit_up_down', 'limit_up_streak']
        
        for table in tables:
            try:
                cursor = conn.execute(f'SELECT COUNT(*) FROM {table}')
                stats[table] = cursor.fetchone()[0]
            except:
                stats[table] = 0
        
        conn.close()
        return stats


def main():
    import argparse
    parser = argparse.ArgumentParser(description='量化数据完整采集器')
    parser.add_argument('--run', action='store_true', help='运行完整采集')
    parser.add_argument('--stats', action='store_true', help='查看统计')
    args = parser.parse_args()
    
    os.makedirs('logs', exist_ok=True)
    
    collector = QuantDataCollector()
    
    if args.run:
        collector.run_all()
    elif args.stats:
        stats = collector.get_stats()
        print("\n" + "=" * 60)
        print("数据统计")
        print("=" * 60)
        for k, v in stats.items():
            print(f"{k}: {v:,}")
        print("=" * 60)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
