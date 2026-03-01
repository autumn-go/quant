#!/usr/bin/env python3
"""
Tushare 历史数据采集器 - 全量采集2014年以来A股个股和指数日K数据
基于之前的 tushare_collector.py 扩展
支持：断点续传、批量采集、指数数据
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
logger.add("logs/tushare_collect.log", rotation="100 MB", level="DEBUG")

# Tushare Token
TOKEN = 'fb3c079912502be08b6fc877031219159d9fcac540ca83f77974ed7714d4'
DB_PATH = "quant_data.db"

# 采集配置
START_DATE = '20140101'  # 2014年1月1日
RATE_LIMIT = 0.05  # 每个请求间隔（秒），避免触发限流


class TushareDataCollector:
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
        logger.info(f"TushareDataCollector initialized, DB: {db_path}")
    
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
        
        conn.commit()
        conn.close()
        logger.info("Database initialized")
    
    # ==================== 股票列表采集 ====================
    
    def fetch_stock_list(self) -> pd.DataFrame:
        """获取A股所有股票列表"""
        logger.info("Fetching A股 stock list from Tushare...")
        
        # 获取基础信息
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
        """获取全量指数列表 - 主要市场"""
        logger.info("Fetching all index list from Tushare...")
        
        all_indices = []
        
        # 获取主要市场指数 - 减少市场数量以加快速度
        markets = ['SSE', 'SZSE', 'CSI']  # 上交所、深交所、中证指数
        
        for market in markets:
            try:
                df = self.pro.index_basic(market=market)
                if df is not None and not df.empty:
                    all_indices.append(df)
                    logger.info(f"Fetched {len(df)} indices from {market}")
                time.sleep(0.05)  # 限速
            except Exception as e:
                logger.warning(f"Failed to fetch {market} indices: {e}")
        
        if not all_indices:
            logger.warning("No index data returned")
            return pd.DataFrame()
        
        # 合并所有指数
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
        
        # 去重
        df = df.drop_duplicates(subset=['symbol'])
        
        logger.info(f"Fetched {len(df)} total indices")
        return df[['symbol', 'code', 'name', 'exchange', 'market', 'list_date', 'industry']]
    
    def save_stock_list(self, df: pd.DataFrame):
        """保存股票列表到数据库"""
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
        logger.info(f"Saved {len(df)} stocks to database")
    
    # ==================== 日线数据采集 ====================
    
    def fetch_daily_data(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取个股日线数据"""
        try:
            df = self.pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
            
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
            
            df['volume'] = df['volume'].astype(float) * 100  # 转为股
            
            return df[['symbol', 'date', 'open', 'high', 'low', 'close', 'volume', 'amount']]
            
        except Exception as e:
            logger.error(f"Failed to fetch {ts_code}: {e}")
            return pd.DataFrame()
    
    def fetch_index_daily(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取指数日线数据"""
        try:
            df = self.pro.index_daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
            
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
            logger.error(f"Failed to fetch index {ts_code}: {e}")
            return pd.DataFrame()
    
    def get_last_update_date(self, symbol: str) -> Optional[str]:
        """获取某只股票最后更新的日期"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute('SELECT last_date FROM collection_progress WHERE symbol = ?', (symbol,))
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0]:
            return result[0]
        
        # 如果没有进度记录，检查实际数据
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute('SELECT MAX(date) FROM daily_prices WHERE symbol = ?', (symbol,))
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result and result[0] else None
    
    def save_daily_prices(self, df: pd.DataFrame):
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
        """更新采集进度"""
        conn = sqlite3.connect(self.db_path)
        conn.execute('''INSERT OR REPLACE INTO collection_progress 
            (symbol, last_date, status, updated_at)
            VALUES (?, ?, ?, ?)''',
            (symbol, last_date, status, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
    
    # ==================== 批量采集 ====================
    
    def collect_symbol(self, symbol: str, is_index: bool = False) -> dict:
        """采集单个标的"""
        try:
            # 确定日期范围
            last_date = self.get_last_update_date(symbol)
            
            if last_date:
                # 增量更新
                start = (datetime.strptime(last_date, '%Y%m%d') + timedelta(days=1)).strftime('%Y%m%d')
            else:
                # 全量更新
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
                return {'symbol': symbol, 'status': 'empty', 'count': 0, 'message': 'No data returned'}
            
            # 保存数据
            count = self.save_daily_prices(df)
            
            # 更新进度
            last_data_date = df['date'].max()
            self.update_progress(symbol, last_data_date, 'completed')
            
            time.sleep(RATE_LIMIT)  # 限速
            
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
        """批量采集所有标的 - 支持断点续传"""
        
        # 获取已完成的标的
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT symbol FROM collection_progress WHERE status = 'completed'")
        completed_symbols = set(row[0] for row in cursor.fetchall())
        conn.close()
        
        # 过滤掉已完成的
        symbols_to_collect = [s for s in symbols if s not in completed_symbols]
        skipped_count = len(symbols) - len(symbols_to_collect)
        
        logger.info(f"Starting to collect {len(symbols_to_collect)} symbols...")
        if skipped_count > 0:
            logger.info(f"Skipped {skipped_count} already completed symbols")
        
        results = []
        start_time = time.time()
        
        for i, symbol in enumerate(symbols_to_collect):
            result = self.collect_symbol(symbol, is_index=is_indices)
            results.append(result)
            
            # 进度显示
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
        """获取统计信息"""
        conn = sqlite3.connect(self.db_path)
        
        cursor = conn.execute('SELECT COUNT(*) FROM stocks')
        stock_count = cursor.fetchone()[0]
        
        cursor = conn.execute('SELECT COUNT(*) FROM daily_prices')
        price_count = cursor.fetchone()[0]
        
        cursor = conn.execute('SELECT COUNT(DISTINCT symbol) FROM daily_prices')
        symbol_with_data = cursor.fetchone()[0]
        
        cursor = conn.execute('''
            SELECT market, COUNT(*) FROM stocks GROUP BY market
        ''')
        market_stats = {row[0]: row[1] for row in cursor.fetchall()}
        
        conn.close()
        
        return {
            'total_stocks': stock_count,
            'total_prices': price_count,
            'symbols_with_data': symbol_with_data,
            'market_breakdown': market_stats
        }


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Tushare历史数据采集器')
    parser.add_argument('--init', action='store_true', help='初始化股票列表')
    parser.add_argument('--full', action='store_true', help='全量采集所有数据(2014至今)')
    parser.add_argument('--update', action='store_true', help='增量更新')
    parser.add_argument('--index', action='store_true', help='只采集指数')
    parser.add_argument('--stock', action='store_true', help='只采集个股')
    parser.add_argument('--symbol', type=str, help='指定股票代码，如000001.SZ')
    parser.add_argument('--stats', action='store_true', help='查看统计信息')
    
    args = parser.parse_args()
    
    # 创建日志目录
    os.makedirs('logs', exist_ok=True)
    
    collector = TushareDataCollector()
    
    if args.init:
        # 初始化股票列表
        stocks_df = collector.fetch_stock_list()
        indices_df = collector.fetch_index_list()
        
        collector.save_stock_list(stocks_df)
        collector.save_stock_list(indices_df)
        
        logger.info(f"Initialized {len(stocks_df)} stocks and {len(indices_df)} indices")
    
    elif args.full or args.update:
        # 采集数据
        mode = "全量" if args.full else "增量"
        logger.info(f"Starting {mode} data collection...")
        
        conn = sqlite3.connect(DB_PATH)
        
        symbols_to_collect = []
        
        # 获取指数
        if args.index or (not args.stock):
            cursor = conn.execute("SELECT symbol FROM stocks WHERE market = '指数'")
            indices = [row[0] for row in cursor.fetchall()]
            symbols_to_collect.extend(indices)
            logger.info(f"Will collect {len(indices)} indices")
        
        # 获取个股
        if args.stock or (not args.index):
            cursor = conn.execute("SELECT symbol FROM stocks WHERE market = 'A股'")
            stocks = [row[0] for row in cursor.fetchall()]
            symbols_to_collect.extend(stocks)
            logger.info(f"Will collect {len(stocks)} stocks")
        
        conn.close()
        
        # 开始采集
        is_indices = args.index and not args.stock
        collector.collect_all(symbols_to_collect, is_indices=is_indices)
    
    elif args.symbol:
        # 采集指定股票
        result = collector.collect_symbol(args.symbol)
        logger.info(f"Result: {result}")
    
    elif args.stats:
        # 查看统计
        stats = collector.get_stats()
        print("\n" + "=" * 60)
        print("数据统计")
        print("=" * 60)
        print(f"股票总数: {stats['total_stocks']}")
        print(f"价格记录数: {stats['total_prices']}")
        print(f"有数据的标的: {stats['symbols_with_data']}")
        print("\n市场分布:")
        for market, count in stats['market_breakdown'].items():
            print(f"  {market}: {count}")
        print("=" * 60)
    
    else:
        parser.print_help()
        print("\n示例:")
        print("  python tushare_historical.py --init              # 初始化股票列表")
        print("  python tushare_historical.py --full              # 全量采集所有数据")
        print("  python tushare_historical.py --full --index      # 只采集指数")
        print("  python tushare_historical.py --update            # 增量更新")
        print("  python tushare_historical.py --symbol 000001.SZ  # 采集单个股票")
        print("  python tushare_historical.py --stats             # 查看统计")


if __name__ == '__main__':
    main()
