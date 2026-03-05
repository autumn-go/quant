"""
SQLite版历史数据采集器 - 用于演示
无需Docker，直接运行
"""

import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple
import sqlite3
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import argparse

# 配置
START_YEAR = 2014
BATCH_SIZE = 100
MAX_WORKERS = 3  # 降低并发避免被封
RATE_LIMIT = 0.5  # 每个请求间隔（秒）

DB_PATH = "quant_data.db"

class SQLiteDataCollector:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.init_db()
        print(f"[INFO] 数据库: {db_path}")
    
    def init_db(self):
        """初始化数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 股票列表表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS stocks (
                    symbol TEXT PRIMARY KEY,
                    code TEXT NOT NULL,
                    name TEXT NOT NULL,
                    exchange TEXT,
                    market TEXT,
                    market_type TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 日线数据表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_prices (
                    symbol TEXT NOT NULL,
                    date TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume INTEGER,
                    amount REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (symbol, date)
                )
            ''')
            
            # 创建索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_price_symbol ON daily_prices(symbol)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_price_date ON daily_prices(date)')
            
            conn.commit()
            print("[INFO] 数据库表初始化完成")
    
    def fetch_a_stock_list(self) -> pd.DataFrame:
        """获取A股所有股票列表"""
        print("[INFO] 获取A股股票列表...")
        
        stocks = []
        
        # 上海
        try:
            sh_df = ak.stock_info_sh_name_code()
            for _, row in sh_df.iterrows():
                code = row['证券代码']
                market_type = '科创板' if code.startswith('688') else '主板'
                stocks.append({
                    'code': code,
                    'name': row['证券简称'],
                    'exchange': 'SH',
                    'market': 'A股',
                    'type': 'stock',
                    'market_type': market_type
                })
            print(f"[INFO] 上海股票: {len(sh_df)}")
        except Exception as e:
            print(f"[ERROR] 上海股票获取失败: {e}")
        
        # 深圳
        try:
            sz_df = ak.stock_info_sz_name_code()
            for _, row in sz_df.iterrows():
                code = row['A股代码']
                market_type = '创业板' if code.startswith('300') else '主板'
                stocks.append({
                    'code': code,
                    'name': row['A股简称'],
                    'exchange': 'SZ',
                    'market': 'A股',
                    'type': 'stock',
                    'market_type': market_type
                })
            print(f"[INFO] 深圳股票: {len(sz_df)}")
        except Exception as e:
            print(f"[ERROR] 深圳股票获取失败: {e}")
        
        # 北交所
        try:
            bj_df = ak.stock_info_bj_name_code()
            for _, row in bj_df.iterrows():
                stocks.append({
                    'code': row['证券代码'],
                    'name': row['证券简称'],
                    'exchange': 'BJ',
                    'market': 'A股',
                    'type': 'stock',
                    'market_type': '北交所'
                })
            print(f"[INFO] 北交所股票: {len(bj_df)}")
        except Exception as e:
            print(f"[ERROR] 北交所股票获取失败: {e}")
        
        df = pd.DataFrame(stocks)
        df['symbol'] = df['code'] + '.' + df['exchange']
        
        print(f"[INFO] 总计A股股票: {len(df)}")
        return df
    
    def fetch_index_list(self) -> pd.DataFrame:
        """获取主要指数列表"""
        print("[INFO] 获取指数列表...")
        
        indices = [
            {'code': '000001', 'name': '上证指数', 'exchange': 'SH', 'type': 'index'},
            {'code': '000016', 'name': '上证50', 'exchange': 'SH', 'type': 'index'},
            {'code': '000300', 'name': '沪深300', 'exchange': 'SH', 'type': 'index'},
            {'code': '000905', 'name': '中证500', 'exchange': 'SH', 'type': 'index'},
            {'code': '000852', 'name': '中证1000', 'exchange': 'SH', 'type': 'index'},
            {'code': '000688', 'name': '科创50', 'exchange': 'SH', 'type': 'index'},
            {'code': '399001', 'name': '深证成指', 'exchange': 'SZ', 'type': 'index'},
            {'code': '399006', 'name': '创业板指', 'exchange': 'SZ', 'type': 'index'},
            {'code': '399673', 'name': '创业板50', 'exchange': 'SZ', 'type': 'index'},
        ]
        
        df = pd.DataFrame(indices)
        df['symbol'] = df['code'] + '.' + df['exchange']
        df['market'] = 'A股'
        df['market_type'] = '指数'
        
        print(f"[INFO] 总计指数: {len(df)}")
        return df
    
    def save_stock_list(self, df: pd.DataFrame):
        """保存股票列表到数据库"""
        print(f"[INFO] 保存 {len(df)} 只股票到数据库...")
        
        with sqlite3.connect(self.db_path) as conn:
            for _, row in df.iterrows():
                conn.execute('''
                    INSERT OR REPLACE INTO stocks (symbol, code, name, exchange, market, market_type)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (row['symbol'], row['code'], row['name'], row['exchange'], 
                      row['market'], row.get('market_type', '')))
            conn.commit()
        
        print("[INFO] 股票列表保存完成")
    
    def fetch_stock_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取个股日线数据"""
        code, exchange = symbol.split('.')
        
        try:
            df = ak.stock_zh_a_hist(
                symbol=code, 
                period="daily",
                start_date=start_date.replace('-', ''),
                end_date=end_date.replace('-', ''),
                adjust="qfq"
            )
            
            if df is None or df.empty:
                return pd.DataFrame()
            
            df = df.rename(columns={
                '日期': 'date',
                '开盘': 'open',
                '收盘': 'close',
                '最高': 'high',
                '最低': 'low',
                '成交量': 'volume',
                '成交额': 'amount',
            })
            
            df['symbol'] = symbol
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
            
            return df[['symbol', 'date', 'open', 'high', 'low', 'close', 'volume', 'amount']]
            
        except Exception as e:
            print(f"[ERROR] 获取 {symbol} 失败: {e}")
            return pd.DataFrame()
    
    def get_last_update_date(self, symbol: str) -> Optional[str]:
        """获取某只股票最后更新的日期"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                'SELECT MAX(date) FROM daily_prices WHERE symbol = ?', (symbol,)
            )
            result = cursor.fetchone()[0]
            return result
    
    def save_daily_prices(self, df: pd.DataFrame) -> int:
        """批量保存日线数据"""
        if df.empty:
            return 0
        
        count = 0
        with sqlite3.connect(self.db_path) as conn:
            for _, row in df.iterrows():
                try:
                    conn.execute('''
                        INSERT OR IGNORE INTO daily_prices 
                        (symbol, date, open, high, low, close, volume, amount)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        row['symbol'], row['date'],
                        float(row['open']), float(row['high']), float(row['low']),
                        float(row['close']), int(row['volume']),
                        float(row['amount']) if pd.notna(row['amount']) else None
                    ))
                    count += 1
                except Exception as e:
                    print(f"[ERROR] 保存 {row['symbol']} {row['date']} 失败: {e}")
            
            conn.commit()
        
        return count
    
    def collect_single_stock(self, symbol: str, name: str) -> Dict:
        """采集单只股票数据"""
        try:
            last_date = self.get_last_update_date(symbol)
            
            if last_date:
                start = (datetime.strptime(last_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
            else:
                start = f"{START_YEAR}-01-01"
            
            end = datetime.now().strftime('%Y-%m-%d')
            
            if start > end:
                return {'symbol': symbol, 'status': 'skipped', 'count': 0}
            
            df = self.fetch_stock_daily(symbol, start, end)
            
            if df.empty:
                return {'symbol': symbol, 'status': 'empty', 'count': 0}
            
            count = self.save_daily_prices(df)
            
            return {
                'symbol': symbol, 
                'status': 'success', 
                'count': count,
                'start': start,
                'end': end
            }
            
        except Exception as e:
            print(f"[ERROR] 采集 {symbol} 失败: {e}")
            return {'symbol': symbol, 'status': 'error', 'count': 0, 'message': str(e)}
    
    def collect_all(self, symbols: List[Tuple[str, str]], max_workers: int = MAX_WORKERS):
        """批量采集多只股票数据"""
        print(f"\n{'='*60}")
        print(f"开始采集 {len(symbols)} 只股票的历史数据")
        print(f"时间范围: {START_YEAR}年至今")
        print(f"并发数: {max_workers}")
        print(f"{'='*60}\n")
        
        results = []
        success_count = 0
        empty_count = 0
        error_count = 0
        total_records = 0
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_symbol = {
                executor.submit(self.collect_single_stock, symbol, name): (symbol, name)
                for symbol, name in symbols
            }
            
            with tqdm(total=len(symbols), desc="采集进度") as pbar:
                for future in as_completed(future_to_symbol):
                    symbol, name = future_to_symbol[future]
                    try:
                        result = future.result()
                        results.append(result)
                        
                        if result['status'] == 'success':
                            success_count += 1
                            total_records += result['count']
                            pbar.set_postfix({
                                '成功': success_count,
                                '记录': total_records
                            })
                        elif result['status'] == 'empty':
                            empty_count += 1
                        else:
                            error_count += 1
                            
                    except Exception as e:
                        error_count += 1
                        print(f"[ERROR] 异常 {symbol}: {e}")
                    
                    pbar.update(1)
                    time.sleep(RATE_LIMIT)
        
        print(f"\n{'='*60}")
        print(f"采集完成!")
        print(f"成功: {success_count} | 空数据: {empty_count} | 失败: {error_count}")
        print(f"总记录数: {total_records}")
        print(f"{'='*60}\n")
        
        return results
    
    def get_stats(self):
        """获取数据统计"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT COUNT(*) FROM stocks')
            stock_count = cursor.fetchone()[0]
            
            cursor = conn.execute('SELECT COUNT(*) FROM daily_prices')
            price_count = cursor.fetchone()[0]
            
            cursor = conn.execute('SELECT COUNT(DISTINCT symbol) FROM daily_prices')
            price_symbol_count = cursor.fetchone()[0]
            
            cursor = conn.execute('SELECT MIN(date), MAX(date) FROM daily_prices')
            date_range = cursor.fetchone()
            
        return {
            'stocks': stock_count,
            'prices': price_count,
            'price_symbols': price_symbol_count,
            'date_range': date_range
        }


def main():
    parser = argparse.ArgumentParser(description='A股历史数据采集器(SQLite版)')
    parser.add_argument('--init', action='store_true', help='初始化股票列表')
    parser.add_argument('--full', action='store_true', help='全量采集')
    parser.add_argument('--update', action='store_true', help='增量更新')
    parser.add_argument('--index', action='store_true', help='只采集指数')
    parser.add_argument('--stock', action='store_true', help='只采集个股')
    parser.add_argument('--limit', type=int, help='限制采集数量（用于测试）')
    
    args = parser.parse_args()
    
    collector = SQLiteDataCollector()
    
    if args.init:
        # 初始化股票列表
        stocks_df = collector.fetch_a_stock_list()
        indices_df = collector.fetch_index_list()
        
        collector.save_stock_list(stocks_df)
        collector.save_stock_list(indices_df)
        
        print(f"\n初始化完成: {len(stocks_df)} 只股票 + {len(indices_df)} 个指数")
    
    elif args.full or args.update:
        mode = "全量" if args.full else "增量"
        print(f"\n开始{mode}采集...")
        
        symbols_to_collect = []
        
        # 获取指数
        if args.index or (not args.stock):
            indices_df = collector.fetch_index_list()
            symbols_to_collect.extend([(row['symbol'], row['name']) for _, row in indices_df.iterrows()])
        
        # 获取个股
        if args.stock or (not args.index):
            stocks_df = collector.fetch_a_stock_list()
            symbols_to_collect.extend([(row['symbol'], row['name']) for _, row in stocks_df.iterrows()])
        
        # 限制数量（测试用）
        if args.limit:
            symbols_to_collect = symbols_to_collect[:args.limit]
            print(f"[测试模式] 只采集前 {args.limit} 只")
        
        # 开始采集
        collector.collect_all(symbols_to_collect)
        
        # 显示统计
        stats = collector.get_stats()
        print("\n数据库统计:")
        print(f"  股票数: {stats['stocks']}")
        print(f"  日线记录: {stats['prices']}")
        print(f"  有数据的股票: {stats['price_symbols']}")
        print(f"  数据范围: {stats['date_range'][0]} ~ {stats['date_range'][1]}")
    
    else:
        # 显示当前统计
        stats = collector.get_stats()
        print("\n当前数据库统计:")
        print(f"  股票数: {stats['stocks']}")
        print(f"  日线记录: {stats['prices']}")
        print(f"  有数据的股票: {stats['price_symbols']}")
        if stats['date_range'][0]:
            print(f"  数据范围: {stats['date_range'][0]} ~ {stats['date_range'][1]}")
        print("\n使用说明:")
        print("  python sqlite_collector.py --init     # 初始化股票列表")
        print("  python sqlite_collector.py --full     # 全量采集")
        print("  python sqlite_collector.py --update   # 增量更新")
        print("  python sqlite_collector.py --full --limit 10  # 测试采集10只")


if __name__ == '__main__':
    main()
