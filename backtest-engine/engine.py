"""
回测引擎
基于Backtrader的事件驱动回测框架
"""

import backtrader as bt
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from shared.models import Backtest, Trade, Stock, DailyPrice
from loguru import logger


@dataclass
class BacktestConfig:
    """回测配置"""
    start_date: datetime
    end_date: datetime
    initial_capital: float = 1000000.0
    commission: float = 0.0003  # 佣金率
    slippage: float = 0.001  # 滑点
    position_sizing: str = "fixed"  # fixed/percent/risk
    position_size: float = 100000  # 固定金额或百分比


class StrategyWrapper(bt.Strategy):
    """策略包装器 - 将用户Python代码包装为Backtrader策略"""
    
    params = (
        ('user_code', ''),
        ('params_json', {}),
    )
    
    def __init__(self):
        self.order = None
        self.buy_price = None
        self.buy_comm = None
        self.trades = []
        
        # 执行用户代码中的初始化逻辑
        self._exec_user_init()
    
    def _exec_user_init(self):
        """执行用户策略的初始化代码"""
        try:
            # 创建安全的执行环境
            namespace = {
                'self': self,
                'bt': bt,
                'pd': pd,
                'params': self.p.params_json,
            }
            
            # 提取用户代码中的 __init__ 部分
            code = self.p.user_code
            if 'def __init__' in code:
                # 简单提取并执行
                exec(code, namespace)
                
        except Exception as e:
            logger.error(f"Error in user strategy init: {e}")
    
    def next(self):
        """每个bar执行"""
        try:
            # 执行用户策略的next逻辑
            namespace = {
                'self': self,
                'data': self.data,
                'position': self.position,
                'bt': bt,
            }
            
            # 这里需要解析用户代码中的next方法
            # 简化版本：直接执行用户代码
            exec(self.p.user_code, namespace)
            
        except Exception as e:
            logger.error(f"Error in user strategy next: {e}")
    
    def notify_order(self, order):
        """订单状态通知"""
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status in [order.Completed]:
            if order.isbuy():
                self.buy_price = order.executed.price
                self.buy_comm = order.executed.comm
                logger.info(f'BUY EXECUTED, Price: {order.executed.price:.2f}, '
                          f'Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')
            else:
                logger.info(f'SELL EXECUTED, Price: {order.executed.price:.2f}, '
                          f'Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')
                
                # 记录交易
                trade = {
                    'date': self.data.datetime.date(0),
                    'action': 'SELL',
                    'price': order.executed.price,
                    'size': order.executed.size,
                    'value': order.executed.value,
                }
                self.trades.append(trade)
        
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            logger.warning('Order Canceled/Margin/Rejected')
        
        self.order = None
    
    def notify_trade(self, trade):
        """交易完成通知"""
        if not trade.isclosed:
            return
        
        logger.info(f'OPERATION PROFIT, GROSS: {trade.pnl:.2f}, NET: {trade.pnlcomm:.2f}')


class BacktestEngine:
    """回测引擎"""
    
    def __init__(self, db_session):
        self.db = db_session
        self.cerebro = None
        self.results = None
    
    def _create_cerebro(self, config: BacktestConfig) -> bt.Cerebro:
        """创建Cerebro引擎"""
        cerebro = bt.Cerebro()
        
        # 设置初始资金
        cerebro.broker.setcash(config.initial_capital)
        
        # 设置佣金
        cerebro.broker.setcommission(commission=config.commission)
        
        # 添加滑点
        cerebro.broker.set_slippage_perc(config.slippage)
        
        # 添加分析器
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
        cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
        
        return cerebro
    
    def _load_data(self, symbol: str, start_date: datetime, end_date: datetime) -> Optional[pd.DataFrame]:
        """从数据库加载股票数据"""
        stock = self.db.query(Stock).filter(Stock.symbol == symbol).first()
        if not stock:
            logger.error(f"Stock not found: {symbol}")
            return None
        
        prices = self.db.query(DailyPrice).filter(
            DailyPrice.stock_id == stock.id,
            DailyPrice.time >= start_date,
            DailyPrice.time <= end_date
        ).order_by(DailyPrice.time).all()
        
        if not prices:
            logger.error(f"No price data for {symbol}")
            return None
        
        df = pd.DataFrame([{
            'datetime': p.time,
            'open': float(p.open),
            'high': float(p.high),
            'low': float(p.low),
            'close': float(p.close),
            'volume': int(p.volume),
        } for p in prices])
        
        df.set_index('datetime', inplace=True)
        return df
    
    def run_backtest(
        self,
        strategy_code: str,
        symbols: List[str],
        config: BacktestConfig,
        strategy_params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        执行回测
        
        :param strategy_code: 用户编写的策略Python代码
        :param symbols: 交易标的列表
        :param config: 回测配置
        :param strategy_params: 策略参数
        :return: 回测结果
        """
        self.cerebro = self._create_cerebro(config)
        
        # 加载数据
        for symbol in symbols:
            df = self._load_data(symbol, config.start_date, config.end_date)
            if df is None:
                continue
            
            data = bt.feeds.PandasData(
                dataname=df,
                datetime=None,  # 使用index
                open='open',
                high='high',
                low='low',
                close='close',
                volume='volume',
            )
            self.cerebro.adddata(data, name=symbol)
        
        if not self.cerebro.datas:
            raise ValueError("No valid data loaded for backtest")
        
        # 添加策略
        self.cerebro.addstrategy(
            StrategyWrapper,
            user_code=strategy_code,
            params_json=strategy_params or {}
        )
        
        # 执行回测
        logger.info(f"Starting backtest from {config.start_date} to {config.end_date}")
        logger.info(f"Initial Capital: {config.initial_capital:,.2f}")
        
        self.results = self.cerebro.run()
        
        # 提取结果
        return self._extract_results(config)
    
    def _extract_results(self, config: BacktestConfig) -> Dict[str, Any]:
        """提取回测结果"""
        if not self.results:
            return {}
        
        strat = self.results[0]
        
        # 获取分析器结果
        sharpe = strat.analyzers.sharpe.get_analysis()
        drawdown = strat.analyzers.drawdown.get_analysis()
        returns = strat.analyzers.returns.get_analysis()
        trades = strat.analyzers.trades.get_analysis()
        
        # 最终结果
        final_value = self.cerebro.broker.getvalue()
        total_return = (final_value - config.initial_capital) / config.initial_capital
        
        result = {
            'final_value': final_value,
            'total_return': total_return,
            'annual_return': returns.get('rnorm100', 0),
            'max_drawdown': drawdown.get('max', {}).get('drawdown', 0),
            'sharpe_ratio': sharpe.get('sharperatio', 0),
            'total_trades': trades.get('total', {}).get('total', 0),
            'winning_trades': trades.get('won', {}).get('total', 0),
            'losing_trades': trades.get('lost', {}).get('total', 0),
            'trades_detail': strat.trades,
        }
        
        logger.info(f"Backtest completed. Total Return: {total_return:.2%}")
        
        return result
    
    def plot(self, filename: Optional[str] = None):
        """绘制回测结果"""
        if self.cerebro:
            self.cerebro.plot(style='candlestick', barup='red', bardown='green')


# ==================== 示例策略模板 ====================

SMA_CROSS_TEMPLATE = '''
class SmaCross(bt.Strategy):
    params = dict(pfast=10, pslow=30)
    
    def __init__(self):
        self.fast_ma = bt.ind.SMA(period=self.p.pfast)
        self.slow_ma = bt.ind.SMA(period=self.p.pslow)
        self.crossover = bt.ind.CrossOver(self.fast_ma, self.slow_ma)
    
    def next(self):
        if not self.position:
            if self.crossover > 0:
                self.buy()
        elif self.crossover < 0:
            self.sell()
'''

MACD_TEMPLATE = '''
class MacdStrategy(bt.Strategy):
    params = dict(fast=12, slow=26, signal=9)
    
    def __init__(self):
        self.macd = bt.ind.MACD(
            period1=self.p.fast,
            period2=self.p.slow,
            period_signal=self.p.signal
        )
    
    def next(self):
        if not self.position:
            if self.macd.macd > self.macd.signal:
                self.buy()
        elif self.macd.macd < self.macd.signal:
            self.sell()
'''

RSI_TEMPLATE = '''
class RsiStrategy(bt.Strategy):
    params = dict(period=14, overbought=70, oversold=30)
    
    def __init__(self):
        self.rsi = bt.ind.RSI(period=self.p.period)
    
    def next(self):
        if not self.position:
            if self.rsi < self.p.oversold:
                self.buy()
        elif self.rsi > self.p.overbought:
            self.sell()
'''


if __name__ == "__main__":
    # 测试
    from shared.models import get_engine, get_session
    
    engine = get_engine("postgresql://quant:quant@localhost:5432/quant_db")
    db = get_session(engine)
    
    bt_engine = BacktestEngine(db)
    
    config = BacktestConfig(
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 12, 31),
        initial_capital=1000000
    )
    
    result = bt_engine.run_backtest(
        strategy_code=SMA_CROSS_TEMPLATE,
        symbols=["000001.SZ"],
        config=config,
        strategy_params={"pfast": 10, "pslow": 30}
    )
    
    print(result)