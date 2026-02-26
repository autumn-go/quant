"""
快速测试脚本 - 验证核心功能
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from shared.models_sqlite import init_db, get_session, Stock, DailyPrice, User, Strategy
# from data_collector.collector import DataCollector  # 使用内置的DataCollectorSQLite
from datetime import datetime, timedelta
from loguru import logger

def test_database():
    """测试数据库连接"""
    logger.info("=== Testing Database ===")
    engine = init_db()
    session = get_session()
    logger.info("✓ Database initialized")
    return session

def test_stock_list(session):
    """测试股票列表采集"""
    logger.info("\n=== Testing Stock List Collection ===")
    
    # 使用SQLite版本的collector
    collector = DataCollectorSQLite(session)
    collector.sync_stock_list()
    
    count = session.query(Stock).count()
    logger.info(f"✓ Total stocks: {count}")
    
    # 显示几个示例
    stocks = session.query(Stock).limit(5).all()
    for s in stocks:
        logger.info(f"  {s.symbol} - {s.name}")

def test_price_data(session):
    """测试价格数据采集"""
    logger.info("\n=== Testing Price Data Collection ===")
    
    collector = DataCollectorSQLite(session)
    
    # 只测试一只股票
    test_stock = session.query(Stock).first()
    if test_stock:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        logger.info(f"Fetching data for {test_stock.symbol} from {start_date.date()} to {end_date.date()}")
        collector.sync_daily_prices(
            symbols=[test_stock.symbol],
            start_date=start_date.strftime('%Y%m%d'),
            end_date=end_date.strftime('%Y%m%d')
        )
        
        count = session.query(DailyPrice).filter(DailyPrice.stock_id == test_stock.id).count()
        logger.info(f"✓ Price records: {count}")

def test_api():
    """测试API服务"""
    logger.info("\n=== Testing API Server ===")
    import requests
    
    try:
        # 测试健康检查
        response = requests.get("http://localhost:8000/health", timeout=5)
        logger.info(f"✓ API Health: {response.json()}")
    except Exception as e:
        logger.warning(f"API not running: {e}")
        logger.info("  Run: python backend/main.py")


class DataCollectorSQLite:
    """适配SQLite的采集器"""
    
    def __init__(self, session):
        self.session = session
    
    def sync_stock_list(self):
        """同步股票列表"""
        import akshare as ak
        import pandas as pd
        
        # A股
        sh_df = ak.stock_info_sh_name_code()
        sh_df = sh_df[['证券代码', '证券简称']].copy()
        sh_df.columns = ['code', 'name']
        sh_df['exchange'] = 'SH'
        
        sz_df = ak.stock_info_sz_name_code()
        sz_df = sz_df[['A股代码', 'A股简称']].copy()
        sz_df.columns = ['code', 'name']
        sz_df['exchange'] = 'SZ'
        
        df = pd.concat([sh_df, sz_df], ignore_index=True)
        df['market'] = 'A股'
        df['symbol'] = df['code'] + '.' + df['exchange']
        
        # 只保存前20只用于测试
        df = df.head(20)
        
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
        
        self.session.commit()
        logger.info(f"Added {len(df)} stocks")
    
    def sync_daily_prices(self, symbols, start_date, end_date):
        """同步日线数据"""
        import akshare as ak
        
        for symbol in symbols:
            stock = self.session.query(Stock).filter_by(symbol=symbol).first()
            if not stock:
                continue
            
            try:
                code = symbol.split('.')[0]
                df = ak.stock_zh_a_hist(symbol=code, period="daily",
                                       start_date=start_date, end_date=end_date, adjust="qfq")
                
                if df.empty:
                    continue
                
                for _, row in df.iterrows():
                    price = DailyPrice(
                        stock_id=stock.id,
                        time=datetime.strptime(row['日期'], '%Y-%m-%d'),
                        open=float(row['开盘']),
                        high=float(row['最高']),
                        low=float(row['最低']),
                        close=float(row['收盘']),
                        volume=int(row['成交量']),
                        amount=float(row['成交额']) if '成交额' in row else 0
                    )
                    self.session.add(price)
                
                self.session.commit()
                logger.info(f"Added {len(df)} prices for {symbol}")
                
            except Exception as e:
                logger.error(f"Failed to fetch {symbol}: {e}")


if __name__ == "__main__":
    logger.info("Starting Quant Platform Quick Test\n")
    
    # 1. 测试数据库
    session = test_database()
    
    # 2. 测试股票列表
    test_stock_list(session)
    
    # 3. 测试价格数据
    test_price_data(session)
    
    # 4. 测试API
    test_api()
    
    logger.info("\n=== Test Completed ===")
    session.close()