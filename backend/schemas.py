"""
Pydantic 数据模型
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


# ==================== 认证 ====================

class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


# ==================== 用户 ====================

class UserCreate(BaseModel):
    username: str
    email: Optional[str] = None
    password: str


class UserResponse(BaseModel):
    id: str
    username: str
    email: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


# ==================== 股票 ====================

class StockResponse(BaseModel):
    id: str
    symbol: str
    code: str
    name: str
    market: str
    exchange: Optional[str]
    industry: Optional[str]
    sector: Optional[str]
    list_date: Optional[datetime]
    
    class Config:
        from_attributes = True


class StockListResponse(BaseModel):
    total: int
    items: List[StockResponse]


# ==================== 价格数据 ====================

class PriceHistoryRequest(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class DailyPriceResponse(BaseModel):
    time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    amount: Optional[Decimal]
    ma5: Optional[Decimal]
    ma10: Optional[Decimal]
    ma20: Optional[Decimal]
    ma60: Optional[Decimal]
    
    class Config:
        from_attributes = True


# ==================== 策略 ====================

class StrategyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    code: str  # Python策略代码
    params: Optional[str] = None  # JSON格式参数
    strategy_type: str = "technical"  # technical/factor/ml


class StrategyResponse(BaseModel):
    id: str
    user_id: str
    name: str
    description: Optional[str]
    code: str
    params: Optional[str]
    strategy_type: str
    version: int
    is_public: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ==================== 回测 ====================

class BacktestCreate(BaseModel):
    strategy_id: str
    start_date: datetime
    end_date: datetime
    initial_capital: Decimal = Field(default=1000000)


class BacktestResponse(BaseModel):
    id: str
    user_id: str
    strategy_id: str
    start_date: datetime
    end_date: datetime
    initial_capital: Decimal
    total_return: Optional[Decimal]
    annual_return: Optional[Decimal]
    max_drawdown: Optional[Decimal]
    sharpe_ratio: Optional[Decimal]
    volatility: Optional[Decimal]
    win_rate: Optional[Decimal]
    profit_factor: Optional[Decimal]
    total_trades: Optional[int]
    status: str
    created_at: datetime
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class TradeResponse(BaseModel):
    id: str
    trade_date: datetime
    action: str  # BUY/SELL
    price: Decimal
    quantity: int
    amount: Decimal
    signal_type: Optional[str]
    reason: Optional[str]
    
    class Config:
        from_attributes = True


class BacktestResult(BaseModel):
    backtest: BacktestResponse
    trades: List[TradeResponse]