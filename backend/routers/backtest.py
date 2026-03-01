"""
回测执行 API
接收策略代码，执行回测，返回结果
"""

import os
import sys
import tempfile
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import backtrader as bt

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from shared.models_sqlite import get_session, Stock, DailyPrice

router = APIRouter(prefix="/backtest", tags=["backtest"])

class BacktestRequest(BaseModel):
    strategy_code: str
    strategy_params: Dict[str, Any] = {}
    symbol: str = "000001.SZ"  # 默认测试股票
    start_date: str = "2024-01-01"
    end_date: str = "2024-12-31"
    initial_capital: float = 1000000.0
    commission: float = 0.0003

class BacktestResult(BaseModel):
    success: bool
    final_value: float
    total_return: float
    annual_return: float
    max_drawdown: float
    sharpe_ratio: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    trades: List[Dict[str, Any]]
    error: str = None

@router.post("/run", response_model=BacktestResult)
async def run_backtest(request: BacktestRequest):
    """执行回测"""
    try:
        # 创建临时文件写入策略代码
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(request.strategy_code)
            temp_file = f.name
        
        # 动态加载策略类
        import importlib.util
        spec = importlib.util.spec_from_file_location("strategy", temp_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # 获取策略类（假设第一个类就是策略）
        strategy_class = None
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and issubclass(attr, bt.Strategy) and attr != bt.Strategy:
                strategy_class = attr
                break
        
        if not strategy_class:
            raise ValueError("No valid strategy class found")
        
        # 获取数据
        session = get_session()
        stock = session.query(Stock).filter(Stock.symbol == request.symbol).first()
        if not stock:
            raise ValueError(f"Stock not found: {request.symbol}")
        
        start = datetime.strptime(request.start_date, '%Y-%m-%d')
        end = datetime.strptime(request.end_date, '%Y-%m-%d')
        
        prices = session.query(DailyPrice).filter(
            DailyPrice.stock_id == stock.id,
            DailyPrice.time >= start,
            DailyPrice.time <= end
        ).order_by(DailyPrice.time).all()
        
        if len(prices) < 30:
            raise ValueError("Not enough price data (need at least 30 days)")
        
        # 创建 DataFrame
        import pandas as pd
        df = pd.DataFrame([{
            'datetime': p.time,
            'open': float(p.open),
            'high': float(p.high),
            'low': float(p.low),
            'close': float(p.close),
            'volume': int(p.volume),
        } for p in prices])
        df.set_index('datetime', inplace=True)
        
        # 运行回测
        cerebro = bt.Cerebro()
        cerebro.broker.setcash(request.initial_capital)
        cerebro.broker.setcommission(commission=request.commission)
        
        # 添加数据
        data = bt.feeds.PandasData(
            dataname=df,
            datetime=None,
            open='open',
            high='high',
            low='low',
            close='close',
            volume='volume',
        )
        cerebro.adddata(data)
        
        # 添加策略
        cerebro.addstrategy(strategy_class, **request.strategy_params)
        
        # 添加分析器
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
        cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
        
        # 运行
        results = cerebro.run()
        strat = results[0]
        
        # 提取结果
        final_value = cerebro.broker.getvalue()
        total_return = (final_value - request.initial_capital) / request.initial_capital
        
        sharpe = strat.analyzers.sharpe.get_analysis()
        drawdown = strat.analyzers.drawdown.get_analysis()
        returns = strat.analyzers.returns.get_analysis()
        trades = strat.analyzers.trades.get_analysis()
        
        # 清理临时文件
        os.unlink(temp_file)
        
        return BacktestResult(
            success=True,
            final_value=round(final_value, 2),
            total_return=round(total_return * 100, 2),
            annual_return=round(returns.get('rnorm100', 0), 2),
            max_drawdown=round(drawdown.get('max', {}).get('drawdown', 0), 2),
            sharpe_ratio=round(sharpe.get('sharperatio', 0) or 0, 2),
            total_trades=trades.get('total', {}).get('total', 0),
            winning_trades=trades.get('won', {}).get('total', 0),
            losing_trades=trades.get('lost', {}).get('total', 0),
            trades=[]  # 简化版本，不返回详细交易记录
        )
        
    except Exception as e:
        import traceback
        return BacktestResult(
            success=False,
            final_value=0,
            total_return=0,
            annual_return=0,
            max_drawdown=0,
            sharpe_ratio=0,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            trades=[],
            error=f"{str(e)}\n{traceback.format_exc()}"
        )