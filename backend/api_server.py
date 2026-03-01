"""
API 数据服务 - 连接前端与数据库
"""

import os
import sys
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from shared.models_sqlite import init_db, get_session, Stock, DailyPrice
from routers.backtest import router as backtest_router

app = FastAPI(title="QuantPro API", version="1.0.0")

# CORS - 允许前端访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 数据模型
class StockResponse(BaseModel):
    id: str
    symbol: str
    name: str
    market: str
    exchange: Optional[str]
    price: Optional[float] = None
    change: Optional[float] = None

class MarketIndexResponse(BaseModel):
    name: str
    code: str
    value: float
    change: float
    trend: str

class PriceData(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int

# 初始化数据库
engine = init_db()

# 注册路由
from routers.backtest import router as backtest_router
app.include_router(backtest_router)

@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.now().isoformat()}

@app.get("/api/stocks", response_model=List[StockResponse])
def get_stocks(
    market: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500)
):
    """获取股票列表"""
    session = get_session()
    try:
        query = session.query(Stock)
        if market:
            query = query.filter(Stock.market == market)
        
        stocks = query.limit(limit).all()
        result = []
        
        for stock in stocks:
            # 获取最新价格
            latest_price = session.query(DailyPrice).filter(
                DailyPrice.stock_id == stock.id
            ).order_by(DailyPrice.time.desc()).first()
            
            # 获取前一天价格计算涨跌
            prev_price = None
            if latest_price:
                prev_price = session.query(DailyPrice).filter(
                    DailyPrice.stock_id == stock.id,
                    DailyPrice.time < latest_price.time
                ).order_by(DailyPrice.time.desc()).first()
            
            change = None
            if latest_price and prev_price:
                change = round((float(latest_price.close) - float(prev_price.close)) / float(prev_price.close) * 100, 2)
            
            result.append(StockResponse(
                id=stock.id,
                symbol=stock.symbol,
                name=stock.name,
                market=stock.market,
                exchange=stock.exchange,
                price=float(latest_price.close) if latest_price else None,
                change=change
            ))
        
        return result
    finally:
        session.close()

@app.get("/api/market/indices")
def get_market_indices():
    """获取市场指数数据（模拟实时）"""
    # 实际应该从数据库或第三方API获取
    # 这里先返回模拟数据
    return [
        {"name": "上证指数", "code": "000001.SH", "value": 4146.63, "change": -0.01, "trend": "neutral", "signal": "观望"},
        {"name": "深证成指", "code": "399001.SZ", "value": 14503.79, "change": 0.19, "trend": "up", "signal": "看多"},
        {"name": "创业板指", "code": "399006.SZ", "value": 2928.84, "change": 0.63, "trend": "up", "signal": "看多"},
        {"name": "沪深300", "code": "000300.SH", "value": 3845.62, "change": -0.15, "trend": "down", "signal": "看空"},
        {"name": "中证500", "code": "000905.SH", "value": 5623.45, "change": 0.32, "trend": "up", "signal": "看多"},
        {"name": "恒生指数", "code": "HSI", "value": 26381.02, "change": -1.44, "trend": "down", "signal": "看空"},
        {"name": "恒生科技", "code": "HSTECH", "value": 5109.33, "change": -2.87, "trend": "down", "signal": "强烈看空"},
        {"name": "纳斯达克", "code": "IXIC", "value": 18285.16, "change": 0.85, "trend": "up", "signal": "看多"},
    ]

@app.get("/api/stocks/{symbol}/prices")
def get_stock_prices(
    symbol: str,
    days: int = Query(30, ge=1, le=365)
):
    """获取股票历史价格"""
    session = get_session()
    try:
        stock = session.query(Stock).filter(Stock.symbol == symbol).first()
        if not stock:
            raise HTTPException(status_code=404, detail="Stock not found")
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        prices = session.query(DailyPrice).filter(
            DailyPrice.stock_id == stock.id,
            DailyPrice.time >= start_date,
            DailyPrice.time <= end_date
        ).order_by(DailyPrice.time).all()
        
        return [
            PriceData(
                date=p.time.strftime('%Y-%m-%d'),
                open=float(p.open),
                high=float(p.high),
                low=float(p.low),
                close=float(p.close),
                volume=int(p.volume)
            )
            for p in prices
        ]
    finally:
        session.close()

@app.get("/api/sectors")
def get_sectors():
    """获取板块数据"""
    return [
        {"name": "人工智能", "change": 5.23, "heat": 95, "trend": "up"},
        {"name": "半导体", "change": 3.87, "heat": 88, "trend": "up"},
        {"name": "新能源", "change": 2.15, "heat": 76, "trend": "up"},
        {"name": "医药生物", "change": -1.23, "heat": 45, "trend": "down"},
        {"name": "银行", "change": 0.56, "heat": 62, "trend": "neutral"},
        {"name": "房地产", "change": -2.34, "heat": 32, "trend": "down"},
        {"name": "有色金属", "change": 4.12, "heat": 82, "trend": "up"},
        {"name": "食品饮料", "change": -0.78, "heat": 55, "trend": "neutral"},
    ]

@app.get("/api/strategies/stats")
def get_strategy_stats():
    """获取策略统计"""
    return [
        {"name": "指数择时", "count": 12, "active": 8, "return": "+15.3%"},
        {"name": "风格轮动", "count": 8, "active": 5, "return": "+8.7%"},
        {"name": "板块轮动", "count": 15, "active": 10, "return": "+22.1%"},
        {"name": "个股策略", "count": 25, "active": 18, "return": "+12.5%"},
    ]

@app.get("/api/signals/recent")
def get_recent_signals():
    """获取最新信号"""
    return [
        {"time": "14:32", "type": "买入", "symbol": "000001.SZ", "name": "平安银行", "strategy": "趋势跟踪", "confidence": 85},
        {"time": "14:28", "type": "卖出", "symbol": "600000.SH", "name": "浦发银行", "strategy": "顶底判断", "confidence": 78},
        {"time": "14:15", "type": "买入", "symbol": "000858.SZ", "name": "五粮液", "strategy": "超跌反弹", "confidence": 82},
        {"time": "14:05", "type": "观望", "symbol": "002415.SZ", "name": "海康威视", "strategy": "形态识别", "confidence": 65},
    ]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)