"""
SQLite 版本的数据库模型（用于快速测试）
"""

from sqlalchemy import create_engine, Column, String, Float, DateTime, Integer, BigInteger, Numeric, Text, Boolean, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from typing import Optional
import uuid
import os

Base = declarative_base()

# ==================== 股票基础信息 ====================

class Stock(Base):
    __tablename__ = "stocks"
    
    id = Column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    symbol = Column(String(20), unique=True, nullable=False, index=True)
    code = Column(String(10), nullable=False)
    name = Column(String(100), nullable=False)
    market = Column(String(10), nullable=False)
    exchange = Column(String(10))
    industry = Column(String(50))
    sector = Column(String(50))
    list_date = Column(DateTime)
    delisted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    prices = relationship("DailyPrice", back_populates="stock")


# ==================== 日线行情数据 ====================

class DailyPrice(Base):
    __tablename__ = "daily_prices"
    
    id = Column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    time = Column(DateTime, nullable=False, index=True)
    stock_id = Column(String(32), ForeignKey("stocks.id"), nullable=False)
    
    open = Column(Numeric(18, 4), nullable=False)
    high = Column(Numeric(18, 4), nullable=False)
    low = Column(Numeric(18, 4), nullable=False)
    close = Column(Numeric(18, 4), nullable=False)
    volume = Column(BigInteger, nullable=False)
    amount = Column(Numeric(20, 4))
    adj_factor = Column(Numeric(18, 10), default=1.0)
    
    ma5 = Column(Numeric(18, 4))
    ma10 = Column(Numeric(18, 4))
    ma20 = Column(Numeric(18, 4))
    ma60 = Column(Numeric(18, 4))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
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
    code = Column(Text, nullable=False)
    params = Column(Text)
    strategy_type = Column(String(20), default="technical")
    version = Column(Integer, default=1)
    is_public = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="strategies")
    backtests = relationship("Backtest", back_populates="strategy")


# ==================== 回测记录 ====================

class Backtest(Base):
    __tablename__ = "backtests"
    
    id = Column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    user_id = Column(String(32), ForeignKey("users.id"), nullable=False)
    strategy_id = Column(String(32), ForeignKey("strategies.id"), nullable=False)
    
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    initial_capital = Column(Numeric(18, 4), default=1000000)
    
    total_return = Column(Numeric(10, 4))
    annual_return = Column(Numeric(10, 4))
    max_drawdown = Column(Numeric(10, 4))
    sharpe_ratio = Column(Numeric(10, 4))
    volatility = Column(Numeric(10, 4))
    win_rate = Column(Numeric(10, 4))
    profit_factor = Column(Numeric(10, 4))
    
    total_trades = Column(Integer)
    winning_trades = Column(Integer)
    losing_trades = Column(Integer)
    
    status = Column(String(20), default="pending")
    error_message = Column(Text)
    result_path = Column(String(255))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    
    user = relationship("User", back_populates="backtests")
    strategy = relationship("Strategy", back_populates="backtests")
    trades = relationship("Trade", back_populates="backtest")


# ==================== 交易记录 ====================

class Trade(Base):
    __tablename__ = "trades"
    
    id = Column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    backtest_id = Column(String(32), ForeignKey("backtests.id"), nullable=False)
    stock_id = Column(String(32), ForeignKey("stocks.id"), nullable=False)
    
    trade_date = Column(DateTime, nullable=False)
    action = Column(String(10), nullable=False)
    price = Column(Numeric(18, 4), nullable=False)
    quantity = Column(Integer, nullable=False)
    amount = Column(Numeric(18, 4), nullable=False)
    
    signal_type = Column(String(20))
    reason = Column(Text)
    position_before = Column(Integer)
    position_after = Column(Integer)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    backtest = relationship("Backtest", back_populates="trades")
    stock = relationship("Stock")


# ==================== 数据库连接 ====================

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'quant.db')
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

def get_engine():
    return create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})

def init_db():
    engine = get_engine()
    Base.metadata.create_all(engine)
    return engine

SessionLocal = sessionmaker(autocommit=False, autoflush=False)

def get_session():
    engine = get_engine()
    SessionLocal.configure(bind=engine)
    return SessionLocal()