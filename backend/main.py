"""
FastAPI 主服务
提供RESTful API接口
"""

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
import os
import sys

# 添加shared目录
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from shared.models_sqlite import (
    Stock, DailyPrice, User, Strategy, Backtest, Trade,
    init_db, get_session
)
from schemas import (
    StockResponse, StockListResponse,
    DailyPriceResponse, PriceHistoryRequest,
    UserCreate, UserResponse,
    StrategyCreate, StrategyResponse,
    BacktestCreate, BacktestResponse, BacktestResult,
    Token, TokenData
)
from loguru import logger

# 配置
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/quant.db")

# FastAPI应用
app = FastAPI(
    title="Quant Platform API",
    description="A港股量化跟踪与回测平台",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 密码加密
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# 数据库
engine = init_db()

# ==================== 依赖注入 ====================

def get_db():
    db = get_session()
    try:
        yield db
    finally:
        db.close()


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    return user


# ==================== 认证接口 ====================

@app.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/users", response_model=UserResponse)
async def create_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_password = get_password_hash(user.password)
    new_user = User(username=user.username, email=user.email, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


# ==================== 股票数据接口 ====================

@app.get("/stocks", response_model=StockListResponse)
async def list_stocks(
    market: Optional[str] = None,
    exchange: Optional[str] = None,
    industry: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """获取股票列表"""
    query = db.query(Stock)
    
    if market:
        query = query.filter(Stock.market == market)
    if exchange:
        query = query.filter(Stock.exchange == exchange)
    if industry:
        query = query.filter(Stock.industry == industry)
    
    total = query.count()
    stocks = query.offset(skip).limit(limit).all()
    
    return {"total": total, "items": stocks}


@app.get("/stocks/{symbol}", response_model=StockResponse)
async def get_stock(symbol: str, db: Session = Depends(get_db)):
    """获取单个股票信息"""
    stock = db.query(Stock).filter(Stock.symbol == symbol).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    return stock


@app.post("/stocks/{symbol}/prices", response_model=List[DailyPriceResponse])
async def get_stock_prices(
    symbol: str,
    request: PriceHistoryRequest,
    db: Session = Depends(get_db)
):
    """获取股票历史价格"""
    stock = db.query(Stock).filter(Stock.symbol == symbol).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    
    query = db.query(DailyPrice).filter(DailyPrice.stock_id == stock.id)
    
    if request.start_date:
        query = query.filter(DailyPrice.time >= request.start_date)
    if request.end_date:
        query = query.filter(DailyPrice.time <= request.end_date)
    
    prices = query.order_by(DailyPrice.time).all()
    return prices


@app.get("/stocks/{symbol}/latest", response_model=DailyPriceResponse)
async def get_latest_price(symbol: str, db: Session = Depends(get_db)):
    """获取最新价格"""
    stock = db.query(Stock).filter(Stock.symbol == symbol).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    
    price = db.query(DailyPrice).filter(
        DailyPrice.stock_id == stock.id
    ).order_by(DailyPrice.time.desc()).first()
    
    if not price:
        raise HTTPException(status_code=404, detail="No price data found")
    
    return price


# ==================== 策略管理接口 ====================

@app.post("/strategies", response_model=StrategyResponse)
async def create_strategy(
    strategy: StrategyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建策略"""
    new_strategy = Strategy(
        user_id=current_user.id,
        name=strategy.name,
        description=strategy.description,
        code=strategy.code,
        params=strategy.params,
        strategy_type=strategy.strategy_type
    )
    db.add(new_strategy)
    db.commit()
    db.refresh(new_strategy)
    return new_strategy


@app.get("/strategies", response_model=List[StrategyResponse])
async def list_strategies(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取当前用户的策略列表"""
    strategies = db.query(Strategy).filter(Strategy.user_id == current_user.id).all()
    return strategies


@app.get("/strategies/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(
    strategy_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取策略详情"""
    strategy = db.query(Strategy).filter(
        Strategy.id == strategy_id,
        Strategy.user_id == current_user.id
    ).first()
    
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    return strategy


@app.put("/strategies/{strategy_id}", response_model=StrategyResponse)
async def update_strategy(
    strategy_id: str,
    strategy_update: StrategyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新策略"""
    strategy = db.query(Strategy).filter(
        Strategy.id == strategy_id,
        Strategy.user_id == current_user.id
    ).first()
    
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    strategy.name = strategy_update.name
    strategy.description = strategy_update.description
    strategy.code = strategy_update.code
    strategy.params = strategy_update.params
    strategy.version += 1
    
    db.commit()
    db.refresh(strategy)
    return strategy


# ==================== 回测接口 ====================

@app.post("/backtests", response_model=BacktestResponse)
async def create_backtest(
    backtest: BacktestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建回测任务"""
    # 验证策略存在
    strategy = db.query(Strategy).filter(
        Strategy.id == backtest.strategy_id,
        Strategy.user_id == current_user.id
    ).first()
    
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    new_backtest = Backtest(
        user_id=current_user.id,
        strategy_id=backtest.strategy_id,
        start_date=backtest.start_date,
        end_date=backtest.end_date,
        initial_capital=backtest.initial_capital,
        status="pending"
    )
    
    db.add(new_backtest)
    db.commit()
    db.refresh(new_backtest)
    
    # TODO: 提交到任务队列执行回测
    
    return new_backtest


@app.get("/backtests", response_model=List[BacktestResponse])
async def list_backtests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取回测历史"""
    backtests = db.query(Backtest).filter(Backtest.user_id == current_user.id).all()
    return backtests


@app.get("/backtests/{backtest_id}", response_model=BacktestResult)
async def get_backtest_result(
    backtest_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取回测结果"""
    backtest = db.query(Backtest).filter(
        Backtest.id == backtest_id,
        Backtest.user_id == current_user.id
    ).first()
    
    if not backtest:
        raise HTTPException(status_code=404, detail="Backtest not found")
    
    trades = db.query(Trade).filter(Trade.backtest_id == backtest_id).all()
    
    return {
        "backtest": backtest,
        "trades": trades
    }


# ==================== 健康检查 ====================

@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow()}


# ==================== ETF数据接口 ====================

@app.get("/api/etf/oversold")
async def get_oversold_etfs(
    rsi_threshold: float = 20.0,
    rsi_period: str = "rsi_6",
    limit: int = 50
):
    """获取超跌ETF列表（RSI < 20）"""
    import sqlite3
    
    DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data-collector", "etf_data.db")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        
        # 验证rsi_period参数
        valid_periods = ["rsi_6", "rsi_12", "rsi_24"]
        if rsi_period not in valid_periods:
            rsi_period = "rsi_6"
        
        # 查询超跌ETF
        query = f"""
        SELECT 
            d.ts_code,
            l.name,
            d.close,
            d.pct_chg,
            d.rsi_6,
            d.rsi_12,
            d.rsi_24,
            d.trade_date
        FROM etf_daily d
        JOIN etf_list l ON d.ts_code = l.ts_code
        WHERE d.{rsi_period} < ?
          AND d.trade_date = (
              SELECT MAX(trade_date) FROM etf_daily
          )
        ORDER BY d.{rsi_period} ASC
        LIMIT ?
        """
        
        cursor = conn.execute(query, (rsi_threshold, limit))
        rows = cursor.fetchall()
        conn.close()
        
        # 转换为响应
        data = []
        for row in rows:
            data.append({
                "ts_code": row["ts_code"],
                "name": row["name"] or row["ts_code"],
                "close": round(row["close"], 3),
                "pct_chg": round(row["pct_chg"], 2) if row["pct_chg"] else 0.0,
                "rsi_6": round(row["rsi_6"], 2) if row["rsi_6"] else None,
                "rsi_12": round(row["rsi_12"], 2) if row["rsi_12"] else None,
                "rsi_24": round(row["rsi_24"], 2) if row["rsi_24"] else None,
                "trade_date": row["trade_date"]
            })
        
        return {"total": len(data), "data": data, "threshold": rsi_threshold}
        
    except Exception as e:
        logger.error(f"查询ETF数据失败: {e}")
        return {"total": 0, "data": [], "threshold": rsi_threshold, "error": str(e)}


@app.get("/api/etf/stats")
async def get_etf_stats():
    """获取ETF统计信息"""
    import sqlite3
    
    DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data-collector", "etf_data.db")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        
        stats = {}
        cursor = conn.execute("SELECT COUNT(*) FROM etf_list")
        stats["total_etfs"] = cursor.fetchone()[0]
        
        cursor = conn.execute("SELECT COUNT(DISTINCT ts_code) FROM etf_daily")
        stats["etfs_with_data"] = cursor.fetchone()[0]
        
        cursor = conn.execute("SELECT COUNT(*) FROM etf_daily")
        stats["total_records"] = cursor.fetchone()[0]
        
        cursor = conn.execute("SELECT MAX(trade_date) FROM etf_daily")
        stats["latest_date"] = cursor.fetchone()[0]
        
        cursor = conn.execute("""
            SELECT COUNT(*) FROM etf_daily
            WHERE rsi_6 < 20
              AND trade_date = (SELECT MAX(trade_date) FROM etf_daily)
        """)
        stats["oversold_count"] = cursor.fetchone()[0]
        
        conn.close()
        return stats
        
    except Exception as e:
        logger.error(f"查询ETF统计失败: {e}")
        return {"error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)