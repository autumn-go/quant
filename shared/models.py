from sqlalchemy import create_engine, Column, String, Float, DateTime, Integer, BigInteger, Numeric, Text, Boolean, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from typing import Optional
import uuid

Base = declarative_base()

# ==================== 股票基础信息 ====================

class Stock(Base):
    __tablename__ = "stocks"
    
    id = Column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    symbol = Column(String(20), unique=True, nullable=False, index=True)  # 如: 000001.SZ
    code = Column(String(10), nullable=False)  # 纯代码: 000001
    name = Column(String(100), nullable=False)  # 平安银行
    market = Column(String(10), nullable=False)  # A股/港股
    exchange = Column(String(10))  # SZ/SH/HK
    industry = Column(String(50))  # 行业
    sector = Column(String(50))  # 板块
    list_date = Column(DateTime)  # 上市日期
    delisted = Column(Boolean, default=False)  # 是否退市
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关联
    prices = relationship("DailyPrice", back_populates="stock")
    
    __table_args__ = (
        Index('idx_stock_market', 'market', 'exchange'),
        Index('idx_stock_industry', 'industry'),
    )


# ==================== 日线行情数据 (TimescaleDB hypertable) ====================

class DailyPrice(Base):
    __tablename__ = "daily_prices"
    
    # TimescaleDB 需要: 时间列 + 唯一标识
    time = Column(DateTime, nullable=False, primary_key=True)
    stock_id = Column(String(32), ForeignKey("stocks.id"), nullable=False, primary_key=True)
    
    # 价格数据
    open = Column(Numeric(18, 4), nullable=False)
    high = Column(Numeric(18, 4), nullable=False)
    low = Column(Numeric(18, 4), nullable=False)
    close = Column(Numeric(18, 4), nullable=False)
    volume = Column(BigInteger, nullable=False)
    amount = Column(Numeric(20, 4))  # 成交额
    
    # 复权因子
    adj_factor = Column(Numeric(18, 10), default=1.0)  # 复权因子
    
    # 技术指标(预计算)
    ma5 = Column(Numeric(18, 4))
    ma10 = Column(Numeric(18, 4))
    ma20 = Column(Numeric(18, 4))
    ma60 = Column(Numeric(18, 4))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关联
    stock = relationship("Stock", back_populates="prices")
    
    __table_args__ = (
        Index('idx_price_stock_time', 'stock_id', 'time'),
    )


# ==================== 用户与策略 ====================

class User(Base):
    __tablename__ = "users"
    
    id = Column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True)
    hashed_password = Column(String(255))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    strategies = relationship("Strategy", back_populates="user")
    backtests = relationship("Backtest", back_populates="user")


class Strategy(Base):
    __tablename__ = "strategies"
    
    id = Column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    user_id = Column(String(32), ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    
    # 策略代码
    code = Column(Text, nullable=False)  # Python代码
    params = Column(Text)  # JSON格式的默认参数
    
    # 策略类型
    strategy_type = Column(String(20), default="technical")  # technical/factor/ml
    
    # 版本控制
    version = Column(Integer, default=1)
    is_public = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关联
    user = relationship("User", back_populates="strategies")
    backtests = relationship("Backtest", back_populates="strategy")


# ==================== 回测记录 ====================

class Backtest(Base):
    __tablename__ = "backtests"
    
    id = Column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    user_id = Column(String(32), ForeignKey("users.id"), nullable=False)
    strategy_id = Column(String(32), ForeignKey("strategies.id"), nullable=False)
    
    # 回测参数
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    initial_capital = Column(Numeric(18, 4), default=1000000)  # 初始资金
    
    # 绩效指标
    total_return = Column(Numeric(10, 4))  # 总收益率
    annual_return = Column(Numeric(10, 4))  # 年化收益率
    max_drawdown = Column(Numeric(10, 4))  # 最大回撤
    sharpe_ratio = Column(Numeric(10, 4))  # 夏普比率
    volatility = Column(Numeric(10, 4))  # 波动率
    win_rate = Column(Numeric(10, 4))  # 胜率
    profit_factor = Column(Numeric(10, 4))  # 盈亏比
    
    # 交易统计
    total_trades = Column(Integer)
    winning_trades = Column(Integer)
    losing_trades = Column(Integer)
    
    # 状态
    status = Column(String(20), default="pending")  # pending/running/completed/failed
    error_message = Column(Text)
    
    # 结果文件路径 (MinIO)
    result_path = Column(String(255))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    
    # 关联
    user = relationship("User", back_populates="backtests")
    strategy = relationship("Strategy", back_populates="backtests")
    trades = relationship("Trade", back_populates="backtest")


# ==================== 交易记录 ====================

class Trade(Base):
    __tablename__ = "trades"
    
    id = Column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    backtest_id = Column(String(32), ForeignKey("backtests.id"), nullable=False)
    stock_id = Column(String(32), ForeignKey("stocks.id"), nullable=False)
    
    # 交易信息
    trade_date = Column(DateTime, nullable=False)
    action = Column(String(10), nullable=False)  # BUY/SELL
    price = Column(Numeric(18, 4), nullable=False)
    quantity = Column(Integer, nullable=False)
    amount = Column(Numeric(18, 4), nullable=False)
    
    # 信号信息
    signal_type = Column(String(20))  # ENTRY/EXIT/STOP/TAKE_PROFIT
    reason = Column(Text)  # 交易理由
    
    # 持仓相关
    position_before = Column(Integer)
    position_after = Column(Integer)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关联
    backtest = relationship("Backtest", back_populates="trades")
    stock = relationship("Stock")
    
    __table_args__ = (
        Index('idx_trade_backtest', 'backtest_id'),
        Index('idx_trade_date', 'trade_date'),
    )


# ==================== 数据库连接 ====================

def get_engine(database_url: str):
    return create_engine(database_url, pool_pre_ping=True, pool_size=10, max_overflow=20)

def init_db(engine):
    Base.metadata.create_all(engine)

SessionLocal = sessionmaker(autocommit=False, autoflush=False)

def get_session(engine):
    SessionLocal.configure(bind=engine)
    return SessionLocal()