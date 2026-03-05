"""
AKShare 数据采集器
负责A股和港股的日线数据采集、清洗、入库
"""

import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import sys
import os

# 添加shared目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from shared.models import Stock, DailyPrice, get_engine, get_session, init_db
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

# 数据库配置
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://quant:quant@localhost:5432/quant_db")

class DataCollector:
    def __init__(self, db_url: str = DATABASE_URL):
        self.engine = get_engine(db_url)
        self.session = get_session(self.engine)
        logger.info(f"DataCollector initialized with DB: {db_url}")
    
    def close(self):
        self.session.close()
    
    # ==================== A股数据采集 ====================
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def fetch_a_stock_list(self) -> pd.DataFrame:
        """获取A股所有股票列表"""
        logger.info("Fetching A股 stock list...")
        
        # 上海
        sh_df = ak.stock_info_sh_name_code()
        sh_df = sh_df[['证券代码', '证券简称']].copy()
        sh_df.columns = ['code', 'name']
        sh_df['exchange'] = 'SH'
        
        # 深圳
        sz_df = ak.stock_info_sz_name_code()
        sz_df = sz_df[['A股代码', 'A股简称']].copy()
        sz_df.columns = ['code', 'name']
        sz_df['exchange'] = 'SZ'
        
        # 北京
        bj_df = ak.stock_info_bj_name_code()
        bj_df = bj_df[['证券代码', '证券简称']].copy()
        bj_df.columns = ['code', 'name']
        bj_df['exchange'] = 'BJ'
        
        df = pd.concat([sh_df, sz_df, bj_df], ignore_index=True)
        df['market'] = 'A股'
        df['symbol'] = df['code'] + '.' + df['exchange']
        
        logger.info(f"Fetched {len(df)} A股 stocks")
        return df
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def fetch_a_stock_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取A股日线数据"""
        code, exchange = symbol.split('.')
        
        if exchange == 'SH':
            df = ak.stock_zh_a_hist(symbol=code, period="daily", 
                                    start_date=start_date, end_date=end_date, adjust="qfq")
        elif exchange == 'SZ':
            df = ak.stock_zh_a_hist(symbol=code, period="daily",
                                    start_date=start_date, end_date=end_date, adjust="qfq")
        else:
            # 北交所
            df = ak.stock_bj_a_hist(symbol=code, period="daily",
                                   start_date=start_date, end_date=end_date, adjust="qfq")
        
        if df.empty:
            return df
        
        # 标准化列名
        df.columns = ['date', 'open', 'close', 'high', 'low', 'volume', 
                     'amount', 'amplitude', 'pct_change', 'change', 'turnover']
        df['symbol'] = symbol
        df['date'] = pd.to_datetime(df['date'])
        
        return df[['symbol', 'date', 'open', 'high', 'low', 'close', 'volume', 'amount']]
    
    # ==================== 港股数据采集 ====================
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def fetch_hk_stock_list(self) -> pd.DataFrame:
        """获取港股所有股票列表"""
        logger.info("Fetching 港股 stock list...")
        
        df = ak.stock_hk_ggt_components_em()
        df = df[['代码', '名称']].copy()
        df.columns = ['code', 'name']
        df['exchange'] = 'HK'
        df['market'] = '港股'
        df['symbol'] = df['code'] + '.HK'
        
        logger.info(f"Fetched {len(df)} 港股 stocks")
        return df
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def fetch_hk_stock_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取港股日线数据"""
        code = symbol.replace('.HK', '')
        
        df = ak.stock_hk_hist(symbol=code, period="daily",
                             start_date=start_date, end_date=end_date, adjust="qfq")
        
        if df.empty:
            return df
        
        df.columns = ['date', 'open', 'close', 'high', 'low', 'volume',
                     'amount', 'amplitude', 'pct_change', 'change', 'turnover']
        df['symbol'] = symbol
        df['date'] = pd.to_datetime(df['date'])
        
        return df[['symbol', 'date', 'open', 'high', 'low', 'close', 'volume', 'amount']]
    
    # ==================== 数据入库 ====================
    
    def sync_stock_list(self):
        """同步股票列表到数据库"""
        # A股
        a_df = self.fetch_a_stock_list()
        self._save_stock_list(a_df)
        
        # 港股
        hk_df = self.fetch_hk_stock_list()
        self._save_stock_list(hk_df)
        
        self.session.commit()
        logger.info("Stock list synced successfully")
    
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
                    exchange=row['exchange']
                )
                self.session.add(stock)
                logger.debug(f"Added stock: {row['symbol']} {row['name']}")
    
    def sync_daily_prices(self, symbols: Optional[List[str]] = None, 
                         start_date: Optional[str] = None,
                         end_date: Optional[str] = None):
        """
        同步日线数据
        :param symbols: 指定股票列表，None则同步所有
        :param start_date: 开始日期 (YYYYMMDD)
        :param end_date: 结束日期 (YYYYMMDD)
        """
        if end_date is None:
            end_date = datetime.now().strftime('%Y%m%d')
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
        
        if symbols is None:
            stocks = self.session.query(Stock).all()
            symbols = [s.symbol for s in stocks]
        
        logger.info(f"Syncing daily prices for {len(symbols)} stocks from {start_date} to {end_date}")
        
        for symbol in symbols:
            try:
                if '.HK' in symbol:
                    df = self.fetch_hk_stock_daily(symbol, start_date, end_date)
                else:
                    df = self.fetch_a_stock_daily(symbol, start_date, end_date)
                
                if not df.empty:
                    self._save_daily_prices(df)
                    
            except Exception as e:
                logger.error(f"Failed to fetch {symbol}: {e}")
                continue
        
        self.session.commit()
        logger.info("Daily prices sync completed")
    
    def _save_daily_prices(self, df: pd.DataFrame):
        """保存日线数据到TimescaleDB"""
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
                existing.open = row['open']
                existing.high = row['high']
                existing.low = row['low']
                existing.close = row['close']
                existing.volume = int(row['volume'])
                existing.amount = row.get('amount', 0)
            else:
                # 新增
                price = DailyPrice(
                    stock_id=stock.id,
                    time=row['date'],
                    open=row['open'],
                    high=row['high'],
                    low=row['low'],
                    close=row['close'],
                    volume=int(row['volume']),
                    amount=row.get('amount', 0)
                )
                self.session.add(price)
    
    def incremental_update(self):
        """增量更新：只更新最近3天的数据"""
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=5)).strftime('%Y%m%d')
        
        self.sync_daily_prices(start_date=start_date, end_date=end_date)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Quant Platform Data Collector")
    parser.add_argument("--init", action="store_true", help="初始化股票列表")
    parser.add_argument("--full", action="store_true", help="全量更新历史数据")
    parser.add_argument("--incr", action="store_true", help="增量更新")
    parser.add_argument("--symbol", type=str, help="指定股票代码")
    
    args = parser.parse_args()
    
    collector = DataCollector()
    
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
            
    finally:
        collector.close()