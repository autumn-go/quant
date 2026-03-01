"""
Tushare 数据采集器
负责A股个股和指数日线数据采集、清洗、入库 (2014年至今)
"""

import tushare as ts
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
import sys
import os
import time

# 添加shared目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from shared.models import Stock, DailyPrice, get_engine, get_session, init_db, Base
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

# 数据库配置
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://quant:quant@localhost:5432/quant_db")
TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")

class TushareCollector:
    def __init__(self, db_url: str = DATABASE_URL, token: str = TUSHARE_TOKEN):
        self.engine = get_engine(db_url)
        self.session = get_session(self.engine)
        
        # 初始化Tushare
        if token:
            ts.set_token(token)
        self.pro = ts.pro_api()
        
        logger.info(f"TushareCollector initialized with DB: {db_url}")
    
    def close(self):
        self.session.close()
    
    # ==================== 股票列表采集 ====================
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def fetch_a_stock_list(self) -> pd.DataFrame:
        """获取A股所有股票列表"""
        logger.info("Fetching A股 stock list from Tushare...")
        
        # 获取基础信息
        df = self.pro.stock_basic(exchange='', list_status='L', 
                                  fields='ts_code,symbol,name,area,industry,list_date,exchange')
        
        if df is None or df.empty:
            logger.warning("No stock data returned from Tushare")
            return pd.DataFrame()
        
        # 标准化列名
        df = df.rename(columns={
            'ts_code': 'ts_code',
            'symbol': 'code',
            'name': 'name',
            'area': 'area',
            'industry': 'industry',
            'list_date': 'list_date',
            'exchange': 'exchange'
        })
        
        # 构建symbol (如: 000001.SZ)
        df['symbol'] = df['ts_code']
        df['market'] = 'A股'
        
        # 转换上市日期
        df['list_date'] = pd.to_datetime(df['list_date'], format='%Y%m%d', errors='coerce')
        
        logger.info(f"Fetched {len(df)} A股 stocks")
        return df[['symbol', 'code', 'name', 'market', 'exchange', 'industry', 'list_date']]
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def fetch_index_list(self) -> pd.DataFrame:
        """获取指数列表"""
        logger.info("Fetching index list from Tushare...")
        
        # 获取主要指数
        df = self.pro.index_basic(market='SSE,SZSE,CSI,CICC,SW,MSCI,CICC'
)
        
        if df is None or df.empty:
            return pd.DataFrame()
        
        df = df.rename(columns={
            'ts_code': 'symbol',
            'name': 'name',
            'market': 'exchange'
        })
        
        df['code'] = df['symbol'].str.split('.').str[0]
        df['market'] = '指数'
        df['industry'] = None
        df['list_date'] = None
        
        # 过滤主要指数
        major_indices = [
            '000001.SH', '000002.SH', '000003.SH', '000016.SH', '000300.SH',  # 上证指数系列
            '000688.SH', '000905.SH',  # 科创50, 中证500
            '399001.SZ', '399006.SZ', '399005.SZ',  # 深证成指, 创业板指, 中小板指
            '399300.SZ', '399905.SZ',  # 沪深300, 中证500(深圳)
            '000016.SH', '000010.SH',  # 上证50, 上证180
        ]
        
        df = df[df['symbol'].isin(major_indices)].copy()
        
        logger.info(f"Fetched {len(df)} 指数")
        return df[['symbol', 'code', 'name', 'market', 'exchange', 'industry', 'list_date']]
    
    # ==================== 日线数据采集 ====================
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def fetch_daily_data(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取日线数据
        :param ts_code: Tushare代码 (如: 000001.SZ)
        :param start_date: 开始日期 (YYYYMMDD)
        :param end_date: 结束日期 (YYYYMMDD)
        """
        try:
            df = self.pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
            
            if df is None or df.empty:
                return pd.DataFrame()
            
            # 标准化列名
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
            
            df['date'] = pd.to_datetime(df['date'])
            df['volume'] = df['volume'].astype(int) * 100  # Tushare成交量是手，转为股
            
            return df[['symbol', 'date', 'open', 'high', 'low', 'close', 'volume', 'amount']]
            
        except Exception as e:
            logger.error(f"Failed to fetch {ts_code}: {e}")
            return pd.DataFrame()
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
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
            
            df['date'] = pd.to_datetime(df['date'])
            df['volume'] = df['volume'].fillna(0).astype(int)
            
            return df[['symbol', 'date', 'open', 'high', 'low', 'close', 'volume', 'amount']]
            
        except Exception as e:
            logger.error(f"Failed to fetch index {ts_code}: {e}")
            return pd.DataFrame()
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def fetch_daily_with_limit(self, ts_code: str, start_date: str, end_date: str, is_index: bool = False) -> pd.DataFrame:
        """带频率限制的日线数据获取"""
        time.sleep(0.05)  # 基础延迟，避免触发限流
        
        if is_index:
            return self.fetch_index_daily(ts_code, start_date, end_date)
        else:
            return self.fetch_daily_data(ts_code, start_date, end_date)
    
    # ==================== 数据入库 ====================
    
    def sync_stock_list(self):
        """同步股票和指数列表到数据库"""
        # A股
        a_df = self.fetch_a_stock_list()
        if not a_df.empty:
            self._save_stock_list(a_df)
        
        # 指数
        index_df = self.fetch_index_list()
        if not index_df.empty:
            self._save_stock_list(index_df)
        
        self.session.commit()
        logger.info("Stock and index list synced successfully")
    
    def _save_stock_list(self, df: pd.DataFrame):
        """保存股票列表"""
        for _, row in df.iterrows():
            existing = self.session.query(Stock).filter_by(symbol=row['symbol']).first()
            if not existing:
                stock = Stock(
                    symbol=row['symbol'],
                    code=row['code'],
                    name=row['name'],
                    market=row['market'],
                    exchange=row['exchange'],
                    industry=row.get('industry'),
                    list_date=row.get('list_date')
                )
                self.session.add(stock)
                logger.debug(f"Added: {row['symbol']} {row['name']}")
    
    def sync_daily_prices(self, symbols: Optional[List[str]] = None, 
                         start_date: Optional[str] = None,
                         end_date: Optional[str] = None,
                         batch_size: int = 100):
        """
        同步日线数据
        :param symbols: 指定股票列表，None则同步所有
        :param start_date: 开始日期 (YYYYMMDD)，默认2014-01-01
        :param end_date: 结束日期 (YYYYMMDD)，默认今天
        :param batch_size: 每批处理数量
        """
        if end_date is None:
            end_date = datetime.now().strftime('%Y%m%d')
        if start_date is None:
            start_date = '20140101'  # 2014年以来
        
        if symbols is None:
            stocks = self.session.query(Stock).all()
            symbols = [s.symbol for s in stocks]
        
        logger.info(f"Syncing daily prices for {len(symbols)} symbols from {start_date} to {end_date}")
        
        # 分批处理
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i+batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}/{(len(symbols)-1)//batch_size + 1} ({len(batch)} symbols)")
            
            for symbol in batch:
                try:
                    is_index = self.session.query(Stock).filter_by(symbol=symbol).first()
                    is_index = is_index.market == '指数' if is_index else False
                    
                    df = self.fetch_daily_with_limit(symbol, start_date, end_date, is_index)
                    
                    if not df.empty:
                        self._save_daily_prices(df)
                        logger.info(f"Saved {len(df)} records for {symbol}")
                    else:
                        logger.warning(f"No data for {symbol}")
                        
                except Exception as e:
                    logger.error(f"Failed to fetch {symbol}: {e}")
                    continue
            
            # 每批提交一次
            self.session.commit()
            logger.info(f"Batch {i//batch_size + 1} committed")
        
        logger.info("Daily prices sync completed")
    
    def _save_daily_prices(self, df: pd.DataFrame):
        """保存日线数据到数据库"""
        for _, row in df.iterrows():
            stock = self.session.query(Stock).filter_by(symbol=row['symbol']).first()
            if not stock:
                continue
            
            # 检查是否已存在
            existing = self.session.query(DailyPrice).filter_by(
                stock_id=stock.id,
                time=row['date']
            ).first()
            
            if existing:
                # 更新
                existing.open = float(row['open'])
                existing.high = float(row['high'])
                existing.low = float(row['low'])
                existing.close = float(row['close'])
                existing.volume = int(row['volume'])
                existing.amount = float(row.get('amount', 0)) if pd.notna(row.get('amount')) else 0
            else:
                # 新增
                price = DailyPrice(
                    stock_id=stock.id,
                    time=row['date'],
                    open=float(row['open']),
                    high=float(row['high']),
                    low=float(row['low']),
                    close=float(row['close']),
                    volume=int(row['volume']),
                    amount=float(row.get('amount', 0)) if pd.notna(row.get('amount')) else 0
                )
                self.session.add(price)
    
    def incremental_update(self, days: int = 5):
        """增量更新：只更新最近N天的数据"""
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
        
        self.sync_daily_prices(start_date=start_date, end_date=end_date)
    
    def get_data_stats(self) -> Dict:
        """获取数据统计"""
        stock_count = self.session.query(Stock).count()
        price_count = self.session.query(DailyPrice).count()
        
        # 各市场统计
        market_stats = {}
        for market in ['A股', '指数']:
            count = self.session.query(Stock).filter_by(market=market).count()
            market_stats[market] = count
        
        return {
            'total_stocks': stock_count,
            'total_price_records': price_count,
            'market_breakdown': market_stats
        }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Tushare Data Collector")
    parser.add_argument("--init", action="store_true", help="初始化股票列表")
    parser.add_argument("--full", action="store_true", help="全量更新历史数据 (2014至今)")
    parser.add_argument("--incr", action="store_true", help="增量更新")
    parser.add_argument("--symbol", type=str, help="指定股票代码")
    parser.add_argument("--stats", action="store_true", help="查看数据统计")
    parser.add_argument("--token", type=str, help="Tushare Token")
    
    args = parser.parse_args()
    
    token = args.token or TUSHARE_TOKEN
    collector = TushareCollector(token=token)
    
    try:
        if args.init:
            collector.sync_stock_list()
        
        if args.full:
            if args.symbol:
                collector.sync_daily_prices(symbols=[args.symbol])
            else:
                collector.sync_daily_prices()
        
        if args.incr:
            collector.incremental_update()
        
        if args.stats:
            stats = collector.get_data_stats()
            print("\n=== 数据统计 ===")
            print(f"股票总数: {stats['total_stocks']}")
            print(f"价格记录数: {stats['total_price_records']}")
            print("\n市场分布:")
            for market, count in stats['market_breakdown'].items():
                print(f"  {market}: {count}")
            
    finally:
        collector.close()
