#!/usr/bin/env python3
"""
Tushare 2026年数据采集器
- 专门采集 2026-01-01 至今的 A股日K数据
- 支持断点续传
- 增量更新
- 输出到 SQLite 便于版本控制
"""

import tushare as ts
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import time
import os
import sys
from typing import List, Optional
from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stderr, level="INFO")
logger.add("logs/collect_2026.log", rotation="50 MB", level="DEBUG")

# Tushare Token
TOKEN = '75d5fb0d2da34ab076f1ab49eaecfac348aaf91faf06246bfcab9f68904c'
DB_PATH = "quant_data_2026.db"

# 采集配置 - 只采集2026年以来
START_DATE = '20260101'  # 2026年1月1日
RATE_LIMIT = 0.05  # 请求间隔（秒）


class Collector2026:
    def __init__(self, token: str = TOKEN, db_path: str = DB_PATH):
        self.token = token
        self.db_path = db_path
        
        # 初始化 Tushare
        ts.set_token(token)
        self.pro = ts.pro_api(token)
        
        # 使用自定义代理
        self.pro._DataApi__token = token
        self.pro._DataApi__http_url = 'http://lianghua.nanyangqiankun.top'
        
        self.init_db()
        logger.info(f"Collector2026 initialized, DB: {db_path}")
    
    def init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # 股票列表表
        c.execute('''CREATE TABLE IF NOT EXISTS stocks (
            symbol TEXT PRIMARY KEY,
            code TEXT,
            name TEXT,
            exchange TEXT,
            market TEXT,
            list_date TEXT,
            industry TEXT
        )''')
        
        # 日线数据表
        c.execute('''CREATE TABLE IF NOT EXISTS daily_prices (
            symbol TEXT,
            date TEXT,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            amount REAL,
            PRIMARY KEY (symbol, date)
        )''')
        
        # 采集进度表
        c.execute('''CREATE TABLE IF NOT EXISTS collection_progress (
            symbol TEXT PRIMARY KEY,
            last_date TEXT,
            status TEXT,
            updated_at TEXT
        )''')
        
        # 元数据表
        c.execute('''CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )''')
        
        conn.commit()
        conn.close()
        logger.info("Database initialized")
    
    def fetch_stock_list(self) -> pd.DataFrame:
        """获取A股所有股票列表"""
        logger.info("Fetching A股 stock list...")
        
        df = self.pro.stock_basic(
            exchange='',
            list_status='L',
            fields='ts_code,symbol,name,area,industry,list_date,exchange'
        )
        
        if df is None or df.empty:
            logger.warning("No stock data returned")
            return pd.DataFrame()
        
        df = df.rename(columns={
            'ts_code': 'symbol',
            'symbol': 'code',
            'name': 'name',
            'area': 'area',
            'industry': 'industry',
            'list_date': 'list_date',
            'exchange': 'exchange'
        })
        df['market'] = 'A股'
        
        logger.info(f"Fetched {len(df)} A股 stocks")
        return df[['symbol', 'code', 'name', 'exchange', 'market', 'list_date', 'industry']]
    
    def fetch_index_list(self) -> pd.DataFrame:
        """获取主要指数列表"""
        logger.info("Fetching index list...")
        
        all_indices = []
        markets = ['SSE', 'SZSE', 'CSI']
        
        for market in markets:
            try:
                df = self.pro.index_basic(market=market)
                if df is not None and not df.empty:
                    all_indices.append(df)
                    logger.info(f"Fetched {len(df)} indices from {market}")
                time.sleep(RATE_LIMIT)
            except Exception as e:
                logger.warning(f"Failed to fetch {market} indices: {e}")
        
        if not all_indices:
            return pd.DataFrame()
        
        df = pd.concat(all_indices, ignore_index=True)
        df = df.rename(columns={
            'ts_code': 'symbol',
            'name': 'name',
            'market': 'exchange'
        })
        df['code'] = df['symbol'].str.split('.').str[0]
        df['market'] = '指数'
        df['list_date'] = None
        df['industry'] = None
        df = df.drop_duplicates(subset=['symbol'])
        
        # 只保留主要指数
        main_indices = ['000001.SH', '000002.SH', '000003.SH', '000016.SH', '000300.SH', 
                       '000905.SH', '399001.SZ', '399006.SZ', '399300.SZ', '399905.SZ',
                       '000688.SH', '399006.SZ', '399673.SZ']
        df = df[df['symbol'].isin(main_indices)]
        
        logger.info(f"Fetched {len(df)} main indices")
        return df[['symbol', 'code', 'name', 'exchange', 'market', 'list_date', 'industry']]
    
    def save_stock_list(self, df: pd.DataFrame):
        """保存股票列表"""
        conn = sqlite3.connect(self.db_path)
        for _, row in df.iterrows():
            conn.execute('''INSERT OR REPLACE INTO stocks 
                (symbol, code, name, exchange, market, list_date, industry)
                VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (row['symbol'], row['code'], row['name'], row['exchange'],
                 row['market'], row['list_date'], row.get('industry'))
            )
        conn.commit()
        conn.close()
        logger.info(f"Saved {len(df)} stocks")
    
    def fetch_daily_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取日线数据"""
        try:
            df = self.pro.daily(ts_code=symbol, start_date=start_date, end_date=end_date)
            
            if df is None or df.empty:
                return pd.DataFrame()
            
            df = df.rename(columns={
                'ts_code': 'symbol',
                'trade_date': 'date',
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'vol': 'volume',
                'amount': 'amount'
            })
            df['volume'] = df['volume'].astype(float) * 100
            
            return df[['symbol', 'date', 'open', 'high', 'low', 'close', 'volume', 'amount']]
            
        except Exception as e:
            logger.error(f"Failed to fetch {symbol}: {e}")
            return pd.DataFrame()
    
    def fetch_index_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取指数日线"""
        try:
            df = self.pro.index_daily(ts_code=symbol, start_date=start_date, end_date=end_date)
            
            if df is None or df.empty:
                return pd.DataFrame()
            
            df = df.rename(columns={
                'ts_code': 'symbol',
                'trade_date': 'date',
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'vol': 'volume',
                'amount': 'amount'
            })
            
            return df[['symbol', 'date', 'open', 'high', 'low', 'close', 'volume', 'amount']]
            
        except Exception as e:
            logger.error(f"Failed to fetch index {symbol}: {e}")
            return pd.DataFrame()
    
    def get_last_update_date(self, symbol: str) -> Optional[str]:
        """获取最后更新日期"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute('SELECT last_date FROM collection_progress WHERE symbol = ?', (symbol,))
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0]:
            return result[0]
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute('SELECT MAX(date) FROM daily_prices WHERE symbol = ?', (symbol,))
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result and result[0] else None
    
    def save_daily_prices(self, df: pd.DataFrame) -> int:
        """保存日线数据"""
        if df.empty:
            return 0
        
        conn = sqlite3.connect(self.db_path)
        count = 0
        
        for _, row in df.iterrows():
            try:
                conn.execute('''INSERT OR REPLACE INTO daily_prices 
                    (symbol, date, open, high, low, close, volume, amount)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                    (row['symbol'], row['date'], row['open'], row['high'],
                     row['low'], row['close'], row['volume'], row.get('amount', 0))
                )
                count += 1
            except Exception as e:
                logger.error(f"Failed to save {row['symbol']} {row['date']}: {e}")
        
        conn.commit()
        conn.close()
        return count
    
    def update_progress(self, symbol: str, last_date: str, status: str = 'completed'):
        """更新进度"""
        conn = sqlite3.connect(self.db_path)
        conn.execute('''INSERT OR REPLACE INTO collection_progress 
            (symbol, last_date, status, updated_at)
            VALUES (?, ?, ?, ?)''',
            (symbol, last_date, status, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
    
    def collect_symbol(self, symbol: str, is_index: bool = False) -> dict:
        """采集单个标的"""
        try:
            # 确定日期范围
            last_date = self.get_last_update_date(symbol)
            
            if last_date:
                start = (datetime.strptime(last_date, '%Y%m%d') + timedelta(days=1)).strftime('%Y%m%d')
            else:
                start = START_DATE
            
            end = datetime.now().strftime('%Y%m%d')
            
            if start > end:
                return {'symbol': symbol, 'status': 'skipped', 'count': 0, 'message': 'Already up to date'}
            
            # 采集数据
            if is_index:
                df = self.fetch_index_daily(symbol, start, end)
            else:
                df = self.fetch_daily_data(symbol, start, end)
            
            if df.empty:
                return {'symbol': symbol, 'status': 'empty', 'count': 0, 'message': 'No data'}
            
            # 保存
            count = self.save_daily_prices(df)
            
            # 更新进度
            last_data_date = df['date'].max()
            self.update_progress(symbol, last_data_date, 'completed')
            
            time.sleep(RATE_LIMIT)
            
            return {
                'symbol': symbol,
                'status': 'success',
                'count': count,
                'start': start,
                'end': end
            }
            
        except Exception as e:
            logger.error(f"Failed to collect {symbol}: {e}")
            self.update_progress(symbol, '', f'error: {str(e)}')
            return {'symbol': symbol, 'status': 'error', 'count': 0, 'message': str(e)}
    
    def collect_all(self, symbols: List[str], is_indices: bool = False):
        """批量采集"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT symbol FROM collection_progress WHERE status = 'completed'")
        completed = set(row[0] for row in cursor.fetchall())
        conn.close()
        
        symbols_to_collect = [s for s in symbols if s not in completed]
        
        logger.info(f"Starting to collect {len(symbols_to_collect)} symbols...")
        logger.info(f"Skipped {len(symbols) - len(symbols_to_collect)} already completed")
        
        results = []
        start_time = time.time()
        
        for i, symbol in enumerate(symbols_to_collect):
            result = self.collect_symbol(symbol, is_index=is_indices)
            results.append(result)
            
            if (i + 1) % 10 == 0 or i == len(symbols_to_collect) - 1:
                elapsed = (time.time() - start_time) / 60
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                progress_pct = (i + 1) / len(symbols_to_collect) * 100
                logger.info(f"[{i+1}/{len(symbols_to_collect)}] {symbol}: {result['status']}, "
                           f"已用 {elapsed:.1f} 分, 速度 {rate:.1f} 个/分, 进度 {progress_pct:.1f}%")
        
        # 统计
        success = sum(1 for r in results if r['status'] == 'success')
        skipped = sum(1 for r in results if r['status'] == 'skipped')
        empty = sum(1 for r in results if r['status'] == 'empty')
        error = sum(1 for r in results if r['status'] == 'error')
        total_records = sum(r.get('count', 0) for r in results)
        
        logger.info("=" * 60)
        logger.info(f"采集完成!")
        logger.info(f"成功: {success}, 跳过: {skipped}, 空数据: {empty}, 错误: {error}")
        logger.info(f"总记录数: {total_records}")
        logger.info(f"总用时: {(time.time() - start_time)/60:.1f} 分钟")
        logger.info("=" * 60)
        
        return results
    
    def get_stats(self) -> dict:
        """获取统计"""
        conn = sqlite3.connect(self.db_path)
        
        cursor = conn.execute('SELECT COUNT(*) FROM stocks')
        stock_count = cursor.fetchone()[0]
        
        cursor = conn.execute('SELECT COUNT(*) FROM daily_prices')
        price_count = cursor.fetchone()[0]
        
        cursor = conn.execute('SELECT COUNT(DISTINCT symbol) FROM daily_prices')
        symbols_with_data = cursor.fetchone()[0]
        
        cursor = conn.execute('SELECT MIN(date), MAX(date) FROM daily_prices')
        date_range = cursor.fetchone()
        
        conn.close()
        
        return {
            'total_stocks': stock_count,
            'total_prices': price_count,
            'symbols_with_data': symbols_with_data,
            'date_range': date_range
        }
    
    def update_meta(self, key: str, value: str):
        """更新元数据"""
        conn = sqlite3.connect(self.db_path)
        conn.execute('INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)', (key, value))
        conn.commit()
        conn.close()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='2026年数据采集器')
    parser.add_argument('--init', action='store_true', help='初始化股票列表')
    parser.add_argument('--full', action='store_true', help='全量采集')
    parser.add_argument('--update', action='store_true', help='增量更新')
    parser.add_argument('--stats', action='store_true', help='查看统计')
    parser.add_argument('--symbol', type=str, help='指定股票代码')
    
    args = parser.parse_args()
    
    os.makedirs('logs', exist_ok=True)
    
    collector = Collector2026()
    
    if args.init:
        stocks_df = collector.fetch_stock_list()
        indices_df = collector.fetch_index_list()
        
        collector.save_stock_list(stocks_df)
        collector.save_stock_list(indices_df)
        
        logger.info(f"Initialized {len(stocks_df)} stocks and {len(indices_df)} indices")
    
    elif args.full or args.update:
        mode = "全量" if args.full else "增量"
        logger.info(f"Starting {mode} collection for 2026...")
        
        conn = sqlite3.connect(DB_PATH)
        
        # 获取所有标的
        cursor = conn.execute("SELECT symbol FROM stocks WHERE market = '指数'")
        indices = [row[0] for row in cursor.fetchall()]
        
        cursor = conn.execute("SELECT symbol FROM stocks WHERE market = 'A股'")
        stocks = [row[0] for row in cursor.fetchall()]
        
        conn.close()
        
        # 先采集指数
        logger.info(f"Collecting {len(indices)} indices...")
        collector.collect_all(indices, is_indices=True)
        
        # 再采集个股
        logger.info(f"Collecting {len(stocks)} stocks...")
        collector.collect_all(stocks, is_indices=False)
        
        # 记录更新时间
        collector.update_meta('last_update', datetime.now().isoformat())
        collector.update_meta('data_range', f'{START_DATE} to {datetime.now().strftime("%Y%m%d")}')
    
    elif args.symbol:
        result = collector.collect_symbol(args.symbol)
        logger.info(f"Result: {result}")
    
    elif args.stats:
        stats = collector.get_stats()
        print("\n" + "=" * 60)
        print("2026年数据统计")
        print("=" * 60)
        print(f"股票总数: {stats['total_stocks']}")
        print(f"价格记录数: {stats['total_prices']}")
        print(f"有数据的标的: {stats['symbols_with_data']}")
        if stats['date_range']:
            print(f"数据范围: {stats['date_range'][0]} ~ {stats['date_range'][1]}")
        print("=" * 60)
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
