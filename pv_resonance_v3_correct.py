#!/usr/bin/env python3
"""
价量共振V3 - 严格按照研报实现

1. BMA50: 收盘价的50日移动平均线
2. AMA5/AMA100: 成交量的自适应移动平均线
3. 价能 = BMA(Today) / BMA(Today-3)
4. 量能 = AMA5 / AMA100
5. 价量共振指标 = 价能 × 量能
6. 多空判断: 5日均线 vs 90日均线
   - 多头市场(5日>90日): 阈值1.125
   - 空头市场(5日<90日): 阈值1.275
7. 趋势强劲下跌过滤: 效率指标>50 且 动量<0
8. 最终持仓 = 步骤6持仓 排除 步骤7下跌状态
"""

import sqlite3
import pandas as pd
import numpy as np

DB_PATH = '/root/.openclaw/workspace/quant-main/data-collector/csi300_data.db'


def load_data():
    """加载数据"""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query('''
        SELECT date, open, high, low, close, volume, amount
        FROM csi300_index_daily ORDER BY date
    ''', conn)
    df['date'] = pd.to_datetime(df['date'])
    df.set_index('date', inplace=True)
    conn.close()
    return df


def calculate_ama(series, span):
    """计算自适应移动平均(EMA近似)"""
    return series.ewm(span=span, adjust=False).mean()


def price_volume_resonance_v3(df):
    """
    价量共振V3 - 严格按研报实现
    """
    data = df.copy()
    
    # 1. BMA50: 收盘价的50日移动平均线
    data['bma50'] = data['close'].rolling(window=50).mean()
    
    # 2. AMA5/AMA100: 成交量的自适应移动平均线
    data['ama5_vol'] = calculate_ama(data['volume'], span=5)
    data['ama100_vol'] = calculate_ama(data['volume'], span=100)
    
    # 3. 价能 = BMA(Today) / BMA(Today-3)
    data['price_energy'] = data['bma50'] / data['bma50'].shift(3)
    
    # 4. 量能 = AMA5 / AMA100
    data['volume_energy'] = data['ama5_vol'] / data['ama100_vol']
    
    # 5. 价量共振指标 = 价能 × 量能
    data['pv_indicator'] = data['price_energy'] * data['volume_energy']
    
    # 6. 多空市场判断: 5日均线 vs 90日均线
    data['ma5'] = data['close'].rolling(window=5).mean()
    data['ma90'] = data['close'].rolling(window=90).mean()
    data['is_bull'] = data['ma5'] > data['ma90']  # 多头市场
    
    # 根据市场状态设置阈值和信号
    # 多头市场: >1.125做多, <1.125平仓
    # 空头市场: >1.275做多, <1.275平仓
    data['threshold'] = np.where(data['is_bull'], 1.125, 1.275)
    
    # 基础持仓信号
    data['position_raw'] = np.where(data['pv_indicator'] > data['threshold'], 1, 0)
    
    # 7. 趋势强劲下跌过滤
    # 收盘价4日加权移动平均
    weights = [0.4, 0.3, 0.2, 0.1]
    data['smooth_close'] = data['close'].rolling(window=4).apply(
        lambda x: np.sum(x * weights), raw=True
    )
    
    # 10日价格效率指标
    price_diff = data['smooth_close'].diff().abs()
    total_movement = price_diff.rolling(window=10).sum()
    net_movement = (data['smooth_close'] - data['smooth_close'].shift(10)).abs()
    data['efficiency'] = (net_movement / total_movement.replace(0, np.nan)) * 100
    
    # 10日动量指标
    data['momentum'] = (data['smooth_close'] - data['smooth_close'].shift(10)) / data['smooth_close'].shift(10)
    
    # 趋势强劲下跌: 效率>50 且 动量<0
    data['strong_downtrend'] = (data['efficiency'] > 50) & (data['momentum'] < 0)
    
    # 8. 最终持仓 = 基础持仓 排除 强劲下跌
    data['position'] = np.where(data['strong_downtrend'], 0, data['position_raw'])
    
    # 延迟1天执行
    data['position'] = data['position'].shift(1).fillna(0)
    
    return data


def backtest(data, initial_capital=1.0):
    """回测"""
    df = data.copy()
    df['daily_return'] = df['close'].pct_change()
    df['strategy_return'] = df['position'] * df['daily_return']
    
    df['market_nav'] = (1 + df['daily_return']).cumprod() * initial_capital
    df['strategy_nav'] = (1 + df['strategy_return']).cumprod() * initial_capital
    
    df['market_nav'] = df['market_nav'].fillna(initial_capital)
    df['strategy_nav'] = df['strategy_nav'].fillna(initial_capital)
    
    df['trade'] = df['position'].diff().abs() > 0
    
    return df


def calculate_metrics(df):
    """计算指标"""
    returns = df['strategy_return'].dropna()
    market_returns = df['daily_return'].dropna()
    
    total_return = df['strategy_nav'].iloc[-1] / 1.0 - 1
    market_return = df['market_nav'].iloc[-1] / 1.0 - 1
    
    n_days = len(returns)
    annual_return = (1 + total_return) ** (252 / n_days) - 1 if total_return > -1 else -1
    market_annual = (1 + market_return) ** (252 / n_days) - 1 if market_return > -1 else -1
    
    volatility = returns.std() * np.sqrt(252) if returns.std() > 0 else 0
    market_volatility = market_returns.std() * np.sqrt(252)
    
    sharpe = annual_return / volatility if volatility > 0 else 0
    market_sharpe = market_annual / market_volatility if market_volatility > 0 else 0
    
    cummax = df['strategy_nav'].cummax()
    max_drawdown = ((df['strategy_nav'] - cummax) / cummax).min()
    
    market_cummax = df['market_nav'].cummax()
    market_max_dd = ((df['market_nav'] - market_cummax) / market_cummax).min()
    
    trades = df[df['trade'] == True]
    
    return {
        '总收益率': f"{total_return*100:.2f}%",
        '年化收益率': f"{annual_return*100:.2f}%",
        '最大回撤': f"{max_drawdown*100:.2f}%",
        '夏普比率': f"{sharpe:.3f}",
        '交易次数': int(len(trades)),
        '持仓天数': int(df['position'].sum()),
        '基准总收益': f"{market_return*100:.2f}%",
        '基准夏普': f"{market_sharpe:.3f}",
        '基准最大回撤': f"{market_max_dd*100:.2f}%"
    }


def main():
    print("="*60)
    print("价量共振V3 - 严格按研报实现")
    print("="*60)
    
    df = load_data()
    print(f"\n数据: {len(df)} 条")
    print(f"时间: {df.index[0].date()} ~ {df.index[-1].date()}")
    
    print("\n计算策略...")
    data = price_volume_resonance_v3(df)
    
    # 统计信号
    bull_days = data['is_bull'].sum()
    bear_days = (~data['is_bull']).sum()
    position_days = data['position_raw'].sum()
    filter_days = data['strong_downtrend'].sum()
    final_position = data['position'].sum()
    
    print(f"\n信号统计:")
    print(f"  多头市场天数: {int(bull_days)}")
    print(f"  空头市场天数: {int(bear_days)}")
    print(f"  基础持仓天数: {int(position_days)}")
    print(f"  过滤下跌天数: {int(filter_days)}")
    print(f"  最终持仓天数: {int(final_position)}")
    
    result = backtest(data)
    metrics = calculate_metrics(result)
    
    print(f"\n" + "="*60)
    print("回测结果 (2023-2026)")
    print("="*60)
    print(f"策略总收益: {metrics['总收益率']}")
    print(f"策略年化:   {metrics['年化收益率']}")
    print(f"策略夏普:   {metrics['夏普比率']}")
    print(f"策略回撤:   {metrics['最大回撤']}")
    print(f"交易次数:   {metrics['交易次数']}")
    print(f"\n基准总收益: {metrics['基准总收益']}")
    print(f"基准夏普:   {metrics['基准夏普']}")
    print(f"基准回撤:   {metrics['基准最大回撤']}")
    
    # 生成图表
    plot_results(result, 'pv_resonance_v3_correct_backtest.png')
    
    return result, metrics


def plot_results(df, save_path='pv_resonance_v3_backtest.png'):
    """绘制回测图表"""
    import matplotlib.pyplot as plt
    plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'SimHei', 'Arial Unicode MS']
    plt.rcParams['axes.unicode_minus'] = False
    
    fig, axes = plt.subplots(4, 1, figsize=(14, 12))
    
    # 图1: 净值曲线
    ax1 = axes[0]
    ax1.plot(df.index, df['market_nav'], label='CSI300 Index', linewidth=1.5, color='gray', alpha=0.7)
    ax1.plot(df.index, df['strategy_nav'], label='PV Resonance V3', linewidth=2, color='#e74c3c')
    
    buy_signals = df[df['position'].diff() > 0]
    sell_signals = df[df['position'].diff() < 0]
    
    if len(buy_signals) > 0:
        ax1.scatter(buy_signals.index, buy_signals['strategy_nav'], 
                   marker='^', color='green', s=60, label='Buy', zorder=5)
    if len(sell_signals) > 0:
        ax1.scatter(sell_signals.index, sell_signals['strategy_nav'], 
                   marker='v', color='red', s=60, label='Sell', zorder=5)
    
    ax1.set_title('Price-Volume Resonance V3 Strategy (2023-2026)', fontsize=14, fontweight='bold')
    ax1.set_ylabel('Net Value')
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)
    
    # 图2: 回撤
    ax2 = axes[1]
    cummax = df['strategy_nav'].cummax()
    drawdown = (df['strategy_nav'] - cummax) / cummax * 100
    market_cummax = df['market_nav'].cummax()
    market_dd = (df['market_nav'] - market_cummax) / market_cummax * 100
    
    ax2.fill_between(df.index, drawdown, 0, alpha=0.5, color='#e74c3c', label='Strategy DD')
    ax2.fill_between(df.index, market_dd, 0, alpha=0.3, color='gray', label='Market DD')
    ax2.set_ylabel('Drawdown (%)')
    ax2.set_title('Drawdown Comparison')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # 图3: 价量共振指标
    ax3 = axes[2]
    ax3.plot(df.index, df['pv_indicator'], label='PV Indicator', color='blue', alpha=0.7)
    ax3.plot(df.index, df['threshold'], label='Threshold', color='red', linestyle='--')
    ax3.axhline(y=1.125, color='green', linestyle=':', alpha=0.5, label='Bull Threshold (1.125)')
    ax3.axhline(y=1.275, color='orange', linestyle=':', alpha=0.5, label='Bear Threshold (1.275)')
    ax3.set_ylabel('PV Indicator')
    ax3.set_title('Price-Volume Resonance Indicator')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    
    # 图4: 仓位
    ax4 = axes[3]
    ax4.fill_between(df.index, 0, df['position'], alpha=0.5, color='green')
    ax4.set_ylabel('Position')
    ax4.set_xlabel('Date')
    ax4.set_title('Position Over Time')
    ax4.set_ylim(-0.1, 1.2)
    ax4.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    print(f"\n图表已保存: {save_path}")
    plt.close()


if __name__ == "__main__":
    main()
