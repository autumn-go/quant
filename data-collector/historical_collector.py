"""
A股历史数据采集器 - 全量采集2014年以来所有日线数据
支持：个股、指数、ETF、可转债
特性：断点续传、增量更新、多线程、自动重试
"""

import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
import sys
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import argparse

# 添加shared目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from shared.models import Stock, DailyPrice, get_engine, get_session, init_db
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

# 配置日志
logger.remove()
logger.add(sys.stderr, level="INFO")
logger.add("logs/historical_data.log", rotation="100 MB", level="DEBUG")

# 数据库配置
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://quant:quant@localhost:5432/quant_db")

# 采集配置
START_YEAR = 2014
BATCH_SIZE = 100  # 每批处理的股票数
MAX_WORKERS = 5   # 并发线程数
RATE_LIMIT = 0.3  # 每个请求间隔（秒）


class HistoricalDataCollector:
    def __init__(self, db_url: str = DATABASE_URL):
        self.engine = get_engine(db_url)
        self.session = get_session(self.engine)
        self.init_timescaledb()
        logger.info(f"HistoricalDataCollector initialized with DB: {db_url}")
    
    def close(self):
        self.session.close()
    
    def init_timescaledb(self):
        """初始化TimescaleDB hypertable"""
        try:
            with self.engine.connect() as conn:
                # 检查是否已经是hypertable
                result = conn.execute(text("""
                    SELECT * FROM timescaledb_information.hypertables 
                    WHERE hypertable_name = 'daily_prices'
                """))
                
                if result.rowcount == 0:
                    # 转换为hypertable
                    conn.execute(text("""
                        SELECT create_hypertable('daily_prices', 'time', 
                                                 chunk_time_interval => INTERVAL '1 month',
                                                 if_not_exists => TRUE)
                    """))
                    logger.info("Created TimescaleDB hypertable for daily_prices")
                conn.commit()
        except Exception as e:
            logger.warning(f"TimescaleDB init warning: {e}")
    
    # ==================== 股票列表采集 ====================
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def fetch_a_stock_list(self) -> pd.DataFrame:
        """获取A股所有股票列表（含指数、ETF）"""
        logger.info("Fetching A股 stock list...")
        
        stocks = []
        
        # 1. 上海主板 + 科创板
        try:
            sh_df = ak.stock_info_sh_name_code()
            for _, row in sh_df.iterrows():
                code = row['证券代码']
                # 60开头是主板，688开头是科创板
                market_type = '科创板' if code.startswith('688') else '主板'
                stocks.append({
                    'code': code,
                    'name': row['证券简称'],
                    'exchange': 'SH',
                    'market': 'A股',
                    'type': 'stock',
                    'market_type': market_type
                })
            logger.info(f"Fetched {len(sh_df)} 上海股票")
        except Exception as e:
            logger.error(f"Failed to fetch SH stocks: {e}")
        
        # 2. 深圳主板 + 创业板
        try:
            sz_df = ak.stock_info_sz_name_code()
            for _, row in sz_df.iterrows():
                code = row['A股代码']
                # 00开头是主板，300开头是创业板
                market_type = '创业板' if code.startswith('300') else '主板'
                stocks.append({
                    'code': code,
                    'name': row['A股简称'],
                    'exchange': 'SZ',
                    'market': 'A股',
                    'type': 'stock',
                    'market_type': market_type
                })
            logger.info(f"Fetched {len(sz_df)} 深圳股票")
        except Exception as e:
            logger.error(f"Failed to fetch SZ stocks: {e}")
        
        # 3. 北交所
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
            logger.info(f"Fetched {len(bj_df)} 北交所股票")
        except Exception as e:
            logger.error(f"Failed to fetch BJ stocks: {e}")
        
        df = pd.DataFrame(stocks)
        df['symbol'] = df['code'] + '.' + df['exchange']
        
        logger.info(f"Total A股 stocks: {len(df)}")
        return df
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def fetch_index_list(self) -> pd.DataFrame:
        """获取主要指数列表"""
        logger.info("Fetching index list...")
        
        indices = [
            # 上证指数
            {'code': '000001', 'name': '上证指数', 'exchange': 'SH', 'type': 'index'},
            {'code': '000016', 'name': '上证50', 'exchange': 'SH', 'type': 'index'},
            {'code': '000300', 'name': '沪深300', 'exchange': 'SH', 'type': 'index'},
            {'code': '000905', 'name': '中证500', 'exchange': 'SH', 'type': 'index'},
            {'code': '000852', 'name': '中证1000', 'exchange': 'SH', 'type': 'index'},
            {'code': '000688', 'name': '科创50', 'exchange': 'SH', 'type': 'index'},
            # 深证指数
            {'code': '399001', 'name': '深证成指', 'exchange': 'SZ', 'type': 'index'},
            {'code': '399006', 'name': '创业板指', 'exchange': 'SZ', 'type': 'index'},
            {'code': '399673', 'name': '创业板50', 'exchange': 'SZ', 'type': 'index'},
            {'code': '399005', 'name': '中小板指', 'exchange': 'SZ', 'type': 'index'},
        ]
        
        df = pd.DataFrame(indices)
        df['symbol'] = df['code'] + '.' + df['exchange']
        df['market'] = 'A股'
        df['market_type'] = '指数'
        
        logger.info(f"Total indices: {len(df)}")
        return df
    
    def save_stock_list(self, df: pd.DataFrame):
        """保存股票列表到数据库"""
        logger.info(f"Saving {len(df)} stocks to database...")
        
        for _, row in df.iterrows():
            try:
                # 检查是否已存在
                existing = self.session.query(Stock).filter_by(symbol=row['symbol']).first()
                
                if existing:
                    # 更新
                    existing.name = row['name']
                    existing.market_type = row.get('market_type', '')
                else:
                    # 新建
                    stock = Stock(
                        symbol=row['symbol'],
                        code=row['code'],
                        name=row['name'],
                        market=row['market'],
                        exchange=row['exchange'],
                        industry=row.get('industry', ''),
                        sector=row.get('sector', '')
                    )
                    self.session.add(stock)
                
                self.session.commit()
            except Exception as e:
                logger.error(f"Failed to save stock {row['symbol']}: {e}")
                self.session.rollback()
        
        logger.info("Stock list saved")
    
    # ==================== 日线数据采集 ====================
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def fetch_stock_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取个股日线数据（前复权）"""
        code, exchange = symbol.split('.')
        
        try:
            # AKShare统一接口
            df = ak.stock_zh_a_hist(
                symbol=code, 
                period="daily",
                start_date=start_date.replace('-', ''),
                end_date=end_date.replace('-', ''),
                adjust="qfq"  # 前复权
            )
            
            if df is None or df.empty:
                return pd.DataFrame()
            
            # 标准化列名
            df = df.rename(columns={
                '日期': 'date',
                '开盘': 'open',
                '收盘': 'close',
                '最高': 'high',
                '最低': 'low',
                '成交量': 'volume',
                '成交额': 'amount',
                '振幅': 'amplitude',
                '涨跌幅': 'pct_change',
                '涨跌额': 'change',
                '换手率': 'turnover'
            })
            
            df['symbol'] = symbol
            df['date'] = pd.to_datetime(df['date'])
            
            return df[['symbol', 'date', 'open', 'high', 'low', 'close', 'volume', 'amount']]
            
        except Exception as e:
            logger.error(f"Failed to fetch {symbol}: {e}")
            return pd.DataFrame()
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def fetch_index_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取指数日线数据"""
        code, exchange = symbol.split('.')
        
        try:
            if exchange == 'SH':
                df = ak.index_zh_a_hist(symbol=code, period="daily",
                                       start_date=start_date.replace('-', ''),
                                       end_date=end_date.replace('-', ''))
            else:
                df = ak.index_zh_a_hist(symbol=code, period="daily",
                                       start_date=start_date.replace('-', ''),
                                       end_date=end_date.replace('-', ''))
            
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
            df['date'] = pd.to_datetime(df['date'])
            
            return df[['symbol', 'date', 'open', 'high', 'low', 'close', 'volume', 'amount']]
            
        except Exception as e:
            logger.error(f"Failed to fetch index {symbol}: {e}")
            return pd.DataFrame()
    
    def get_last_update_date(self, symbol: str) -> Optional[str]:
        """获取某只股票最后更新的日期"""
        try:
            stock = self.session.query(Stock).filter_by(symbol=symbol).first()
            if not stock:
                return None
            
            result = self.session.query(DailyPrice).filter_by(stock_id=stock.id)\
                .order_by(DailyPrice.time.desc()).first()
            
            if result:
                return result.time.strftime('%Y-%m-%d')
            return None
        except Exception as e:
            logger.error(f"Failed to get last update date for {symbol}: {e}")
            return None
    
    def save_daily_prices(self, df: pd.DataFrame):
        """批量保存日线数据（使用upsert）"""
        if df.empty:
            return 0
        
        saved_count = 0
        
        for _, row in df.iterrows():
            try:
                # 获取stock_id
                stock = self.session.query(Stock).filter_by(symbol=row['symbol']).first()
                if not stock:
                    logger.warning(f"Stock not found: {row['symbol']}")
                    continue
                
                # 使用INSERT ON CONFLICT DO NOTHING避免重复
                stmt = insert(DailyPrice).values(
                    time=row['date'],
                    stock_id=stock.id,
                    open=float(row['open']),
                    high=float(row['high']),
                    low=float(row['low']),
                    close=float(row['close']),
                    volume=int(row['volume']),
                    amount=float(row['amount']) if pd.notna(row['amount']) else None
                ).on_conflict_do_nothing(
                    index_elements=['time', 'stock_id']
                )
                
                result = self.session.execute(stmt)
                if result.rowcount > 0:
                    saved_count += 1
                
                # 每100条提交一次
                if saved_count % 100 == 0:
                    self.session.commit()
                    
            except Exception as e:
                logger.error(f"Failed to save price for {row['symbol']} {row['date']}: {e}")
                self.session.rollback()
        
        # 最终提交
        self.session.commit()
        return saved_count
    
    def collect_single_stock(self, symbol: str, name: str, is_index: bool = False) -> Dict:
        """采集单只股票数据"""
        try:
            # 确定采集日期范围
            last_date = self.get_last_update_date(symbol)
            
            if last_date:
                # 增量更新：从上次更新日期的下一天开始
                start = (datetime.strptime(last_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
            else:
                # 全量更新：从2014年开始
                start = f"{START_YEAR}-01-01"
            
            end = datetime.now().strftime('%Y-%m-%d')
            
            # 如果已经是最新数据，跳过
            if start > end:
                return {'symbol': symbol, 'status': 'skipped', 'count': 0, 'message': 'Already up to date'}
            
            # 采集数据
            if is_index:
                df = self.fetch_index_daily(symbol, start, end)
            else:
                df = self.fetch_stock_daily(symbol, start, end)
            
            if df.empty:
                return {'symbol': symbol, 'status': 'empty', 'count': 0, 'message': 'No data returned'}
            
            # 保存数据
            count = self.save_daily_prices(df)
            
            return {
                'symbol': symbol, 
                'status': 'success', 
                'count': count,
                'start': start,
                'end': end
            }
            
        except Exception as e:
            logger.error(f"Failed to collect {symbol}: {e}")
            return {'symbol': symbol, 'status': 'error', 'count': 0, 'message': str(e)}
    
    def collect_all_stocks(self, symbols: List[Tuple[str, str]], is_index: bool = False):
        """批量采集多只股票数据（多线程）"""
        logger.info(f"Starting to collect {len(symbols)} stocks...")
        
        results = []
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # 提交所有任务
            future_to_symbol = {
                executor.submit(self.collect_single_stock, symbol, name, is_index): (symbol, name)
                for symbol, name in symbols
            }
            
            # 使用tqdm显示进度
            with tqdm(total=len(symbols), desc="Collecting") as pbar:
                for future in as_completed(future_to_symbol):
                    symbol, name = future_to_symbol[future]
                    try:
                        result = future.result()
                        results.append(result)
                        
                        # 更新进度条描述
                        if result['status'] == 'success':
                            pbar.set_postfix({'last': f"{symbol}: {result['count']}条"})
                        
                    except Exception as e:
                        logger.error(f"Exception for {symbol}: {e}")
                        results.append({'symbol': symbol, 'status': 'exception', 'message': str(e)})
                    
                    pbar.update(1)
                    
                    # 限速
                    time.sleep(RATE_LIMIT)
        
        # 统计结果
        success_count = sum(1 for r in results if r['status'] == 'success')
        empty_count = sum(1 for r in results if r['status'] == 'empty')
        error_count = sum(1 for r in results if r['status'] in ['error', 'exception'])
        total_records = sum(r.get('count', 0) for r in results)
        
        logger.info(f"\n{'='*50}")
        logger.info(f"Collection completed!")
        logger.info(f"Success: {success_count}, Empty: {empty_count}, Error: {error_count}")
        logger.info(f"Total records saved: {total_records}")
        logger.info(f"{'='*50}\n")
        
        return results


def main():
    parser = argparse.ArgumentParser(description='A股历史数据采集器')
    parser.add_argument('--init', action='store_true', help='初始化股票列表')
    parser.add_argument('--full', action='store_true', help='全量采集所有数据')
    parser.add_argument('--update', action='store_true', help='增量更新')
    parser.add_argument('--index', action='store_true', help='只采集指数')
    parser.add_argument('--stock', action='store_true', help='只采集个股')
    parser.add_argument('--symbol', type=str, help='指定股票代码，如000001.SZ')
    
    args = parser.parse_args()
    
    # 创建日志目录
    os.makedirs('logs', exist_ok=True)
    
    collector = HistoricalDataCollector()
    
    try:
        if args.init:
            # 初始化股票列表
            stocks_df = collector.fetch_a_stock_list()
            indices_df = collector.fetch_index_list()
            
            collector.save_stock_list(stocks_df)
            collector.save_stock_list(indices_df)
            
            logger.info(f"Initialized {len(stocks_df)} stocks and {len(indices_df)} indices")
        
        elif args.full or args.update:
            # 采集数据
            mode = "全量" if args.full else "增量"
            logger.info(f"Starting {mode} data collection...")
            
            symbols_to_collect = []
            
            # 获取指数
            if args.index or (not args.stock):
                indices_df = collector.fetch_index_list()
                symbols_to_collect.extend([(row['symbol'], row['name']) for _, row in indices_df.iterrows()])
            
            # 获取个股
            if args.stock or (not args.index):
                stocks_df = collector.fetch_a_stock_list()
                symbols_to_collect.extend([(row['symbol'], row['name']) for _, row in stocks_df.iterrows()])
            
            # 开始采集
            is_index_list = [args.index] * len(symbols_to_collect) if args.index else [False] * len(symbols_to_collect)
            collector.collect_all_stocks(symbols_to_collect, is_index=False)
        
        elif args.symbol:
            # 采集指定股票
            result = collector.collect_single_stock(args.symbol, args.symbol)
            logger.info(f"Result: {result}")
        
        else:
            parser.print_help()
    
    finally:
        collector.close()


if __name__ == '__main__':
    main()
