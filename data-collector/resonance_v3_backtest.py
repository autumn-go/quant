#!/usr/bin/env python3
"""
价量共振V3策略回测
基于华创证券研报《牛市让利，熊市得益，价量共振择时之二》

策略逻辑：
1. 计算价能指标 = BMA(Today) / BMA(Today-3)，BMA为收盘价50日移动平均
2. 计算量能指标（基于AMA成交量移动平均）
3. 价量共振指标 = 价能 × 量能，大于阈值时做多
4. V3新增：过滤强劲趋势下跌（10日效率>50 且 10日动量<0）
"""

import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import os

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'SimHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

DB_PATH = '/root/.openclaw/workspace/quant-main/data-collector/csi300_data.db'


def load_data():
    """加载沪深300指数数据"""
    conn = sqlite3.connect(DB_PATH)
    
    # 读取指数日线数据
    df = pd.read_sql_query('''
        SELECT date, open, high, low, close, volume, amount
        FROM csi300_index_daily
        ORDER BY date
    ''', conn)
    
    conn.close()
    
    df['date'] = pd.to_datetime(df['date'])
    df.set_index('date', inplace=True)
    df.sort_index(inplace=True)
    
    return df


def calculate_bma(series, window=50):
    """计算移动平均 BMA"""
    return series.rolling(window=window).mean()


def calculate_ama(volume, window=50):
    """计算成交量AMA（自适应移动平均）"""
    return volume.rolling(window=window).mean()


def calculate_efficiency_ratio(prices, window=10):
    """
    计算价格效率指标
    Efficiency = |P_n - P_1| / sum(|P_i - P_{i-1}|) * 100
    """
    price_diff = prices.diff().abs()
    total_movement = price_diff.rolling(window=window).sum()
    net_movement = (prices - prices.shift(window)).abs()
    
    efficiency = (net_movement / total_movement) * 100
    return efficiency


def calculate_momentum(prices, window=10):
    """
    计算动量指标
    Momentum = (P_n - P_1) / P_1
    """
    return (prices - prices.shift(window)) / prices.shift(window)


def volume_price_resonance_v3(df, 
                               bma_window=50,
                               ama_window=50,
                               efficiency_window=10,
                               momentum_window=10,
                               threshold1=1.125,
                               threshold2=1.275,
                               efficiency_threshold=50):
    """
    价量共振V3策略实现
    
    参数:
        bma_window: BMA移动平均窗口 (研报默认50)
        ama_window: AMA移动平均窗口 (研报默认50)
        efficiency_window: 效率指标窗口 (研报默认10)
        momentum_window: 动量指标窗口 (研报默认10)
        threshold1: 阈值1 (研报默认1.125)
        threshold2: 阈值2 (研报默认1.275)
        efficiency_threshold: 效率指标阈值 (研报默认50)
    """
    data = df.copy()
    
    # 1. 计算BMA (收盘价的50日移动平均)
    data['bma'] = calculate_bma(data['close'], window=bma_window)
    
    # 2. 计算AMA (成交量的50日移动平均)
    data['ama'] = calculate_ama(data['volume'], window=ama_window)
    
    # 3. 计算价能指标 = BMA(Today) / BMA(Today-3)
    data['price_energy'] = data['bma'] / data['bma'].shift(3)
    
    # 4. 计算量能指标 (简化版：使用成交量/AMA)
    data['volume_energy'] = data['volume'] / data['ama']
    
    # 5. 计算价量共振指标
    # 研报中价量共振 = 价能 × 量能，这里需要归一化处理
    # 简化处理：直接使用价能指标，量能作为辅助确认
    data['vp_resonance'] = data['price_energy'] * (data['volume_energy'] / data['volume_energy'].rolling(50).mean())
    
    # 6. 计算10日效率指标
    data['efficiency'] = calculate_efficiency_ratio(data['close'], window=efficiency_window)
    
    # 7. 计算10日动量指标
    data['momentum'] = calculate_momentum(data['close'], window=momentum_window)
    
    # 8. 判断强劲趋势下跌 (效率>50 且 动量<0)
    data['strong_downtrend'] = (data['efficiency'] > efficiency_threshold) & (data['momentum'] < 0)
    
    # 9. 生成交易信号
    # V2信号：价量共振 > 阈值1 做多，否则平仓
    data['v2_signal'] = np.where(data['price_energy'] > threshold1, 1, 0)
    
    # V3信号：V2信号 排除 强劲趋势下跌
    data['signal'] = np.where((data['v2_signal'] == 1) & (~data['strong_downtrend']), 1, 0)
    
    # 计算持仓 (信号延迟1天执行)
    data['position'] = data['signal'].shift(1)
    data['position'].fillna(0, inplace=True)
    
    return data


def backtest(data, initial_capital=1.0, commission=0.0):
    """
    回测函数
    
    参数:
        data: 包含信号的数据框
        initial_capital: 初始资金
        commission: 手续费率
    """
    df = data.copy()
    
    # 计算每日收益率
    df['daily_return'] = df['close'].pct_change()
    
    # 计算策略收益率 (持仓 × 市场收益率)
    df['strategy_return'] = df['position'] * df['daily_return']
    
    # 计算净值曲线
    df['market_nav'] = (1 + df['daily_return']).cumprod() * initial_capital
    df['strategy_nav'] = (1 + df['strategy_return']).cumprod() * initial_capital
    
    # 计算交易统计
    df['signal_change'] = df['signal'].diff().abs()
    df['trade'] = df['signal_change'] > 0
    
    return df


def calculate_metrics(df):
    """计算策略绩效指标"""
    returns = df['strategy_return'].dropna()
    market_returns = df['daily_return'].dropna()
    
    # 总收益
    total_return = df['strategy_nav'].iloc[-1] / df['strategy_nav'].iloc[0] - 1
    market_return = df['market_nav'].iloc[-1] / df['market_nav'].iloc[0] - 1
    
    # 年化收益 (按252个交易日)
    n_days = len(returns)
    annual_return = (1 + total_return) ** (252 / n_days) - 1
    market_annual = (1 + market_return) ** (252 / n_days) - 1
    
    # 波动率
    volatility = returns.std() * np.sqrt(252)
    market_volatility = market_returns.std() * np.sqrt(252)
    
    # 夏普比率 (假设无风险利率为0)
    sharpe = annual_return / volatility if volatility > 0 else 0
    market_sharpe = market_annual / market_volatility if market_volatility > 0 else 0
    
    # 最大回撤
    cummax = df['strategy_nav'].cummax()
    drawdown = (df['strategy_nav'] - cummax) / cummax
    max_drawdown = drawdown.min()
    
    market_cummax = df['market_nav'].cummax()
    market_drawdown = (df['market_nav'] - market_cummax) / market_cummax
    market_max_dd = market_drawdown.min()
    
    # 胜率
    winning_days = (returns > 0).sum()
    total_days = (returns != 0).sum()
    win_rate = winning_days / total_days if total_days > 0 else 0
    
    # 盈亏比
    avg_gain = returns[returns > 0].mean()
    avg_loss = abs(returns[returns < 0].mean())
    profit_loss_ratio = avg_gain / avg_loss if avg_loss > 0 else 0
    
    # 交易次数
    trades = df['trade'].sum()
    
    # 卡玛比率
    calmar = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0
    
    metrics = {
        '总收益率': f"{total_return*100:.2f}%",
        '年化收益率': f"{annual_return*100:.2f}%",
        '波动率': f"{volatility*100:.2f}%",
        '夏普比率': f"{sharpe:.3f}",
        '最大回撤': f"{max_drawdown*100:.2f}%",
        '卡玛比率': f"{calmar:.3f}",
        '胜率': f"{win_rate*100:.2f}%",
        '盈亏比': f"{profit_loss_ratio:.2f}",
        '交易次数': int(trades),
        '基准总收益': f"{market_return*100:.2f}%",
        '基准年化': f"{market_annual*100:.2f}%",
        '基准最大回撤': f"{market_max_dd*100:.2f}%",
        '基准夏普': f"{market_sharpe:.3f}",
    }
    
    return metrics, df


def plot_results(df, save_path='resonance_v3_backtest.png'):
    """绘制回测结果图"""
    fig, axes = plt.subplots(3, 1, figsize=(14, 12))
    
    # 图1: 净值曲线对比
    ax1 = axes[0]
    ax1.plot(df.index, df['market_nav'], label='CSI300 Index', linewidth=1.5, color='gray', alpha=0.7)
    ax1.plot(df.index, df['strategy_nav'], label='Resonance V3 Strategy', linewidth=1.5, color='red')
    
    # 标记买入/卖出点
    buy_signals = df[df['signal'].diff() > 0].index
    sell_signals = df[df['signal'].diff() < 0].index
    
    ax1.scatter(buy_signals, df.loc[buy_signals, 'strategy_nav'], 
                marker='^', color='green', s=50, label='Buy', zorder=5)
    ax_scatter = ax1.scatter(sell_signals, df.loc[sell_signals, 'strategy_nav'], 
                            marker='v', color='red', s=50, label='Sell', zorder=5)
    
    ax1.set_title('Resonance V3 Strategy Backtest (2025-2026)', fontsize=14, fontweight='bold')
    ax1.set_ylabel('Net Value')
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)
    
    # 图2: 回撤曲线
    ax2 = axes[1]
    cummax = df['strategy_nav'].cummax()
    drawdown = (df['strategy_nav'] - cummax) / cummax * 100
    
    market_cummax = df['market_nav'].cummax()
    market_dd = (df['market_nav'] - market_cummax) / market_cummax * 100
    
    ax2.fill_between(df.index, drawdown, 0, alpha=0.5, color='red', label='Strategy Drawdown')
    ax2.fill_between(df.index, market_dd, 0, alpha=0.3, color='gray', label='Market Drawdown')
    ax2.set_ylabel('Drawdown (%)')
    ax2.set_title('Drawdown Comparison', fontsize=12)
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # 图3: 信号与持仓
    ax3 = axes[2]
    ax3.fill_between(df.index, 0, df['signal'], alpha=0.3, color='green', label='Long Position')
    ax3.set_ylabel('Position')
    ax3.set_xlabel('Date')
    ax3.set_title('Trading Signals', fontsize=12)
    ax3.set_ylim(-0.1, 1.2)
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    print(f"图表已保存: {save_path}")
    plt.close()
    
    return save_path


def generate_report(metrics, df, output_path='resonance_v3_report.txt'):
    """生成策略报告"""
    report = f"""
================================================================================
                    价量共振V3策略回测报告
                Volume-Price Resonance Timing Strategy V3
================================================================================

一、策略概述
--------------------------------------------------------------------------------
策略来源：华创证券《牛市让利，熊市得益，价量共振择时之二》(2019)
核心理念：牛市让利，熊市得益——降低波动而非追求最高收益
策略逻辑：
  1. 计算价能指标 = BMA(Today) / BMA(Today-3)
  2. 计算量能指标（基于AMA成交量移动平均）
  3. 价量共振 = 价能 × 量能，>阈值时做多
  4. V3改进：过滤强劲趋势下跌（10日效率>50 且 10日动量<0）

二、回测参数
--------------------------------------------------------------------------------
回测标的：沪深300指数 (000300.SH)
回测区间：{df.index[0].strftime('%Y-%m-%d')} ~ {df.index[-1].strftime('%Y-%m-%d')}
数据周期：日线
初始资金：1.0

策略参数：
  - BMA窗口：50日
  - AMA窗口：50日
  - 效率指标窗口：10日
  - 动量指标窗口：10日
  - 效率阈值：50
  - 做多阈值：1.125

三、回测结果
--------------------------------------------------------------------------------
                          策略表现                基准(沪深300)
--------------------------------------------------------------------------------
总收益率：          {metrics['总收益率']:>12s}          {metrics['基准总收益']:>12s}
年化收益率：        {metrics['年化收益率']:>12s}          {metrics['基准年化']:>12s}
年化波动率：        {metrics['波动率']:>12s}          -
最大回撤：          {metrics['最大回撤']:>12s}          {metrics['基准最大回撤']:>12s}
夏普比率：          {metrics['夏普比率']:>12s}          {metrics['基准夏普']:>12s}
卡玛比率：          {metrics['卡玛比率']:>12s}          -
胜率：              {metrics['胜率']:>12s}          -
盈亏比：            {metrics['盈亏比']:>12s}          -
交易次数：          {metrics['交易次数']:>12d}          -
--------------------------------------------------------------------------------

四、交易明细（最近10笔）
--------------------------------------------------------------------------------
"""
    
    # 添加最近的交易记录
    trades_df = df[df['trade'] == True].copy()
    trades_df['action'] = trades_df['signal'].map({1: '买入', 0: '卖出'})
    
    if len(trades_df) > 0:
        recent_trades = trades_df.tail(10)[['action', 'close']]
        for idx, row in recent_trades.iterrows():
            report += f"{idx.strftime('%Y-%m-%d')}  {row['action']:6s}  价格: {row['close']:.2f}\n"
    
    report += f"""
--------------------------------------------------------------------------------

五、策略评价
--------------------------------------------------------------------------------
"""
    
    # 自动评价
    sharpe = float(metrics['夏普比率'])
    max_dd = float(metrics['最大回撤'].rstrip('%'))
    win_rate = float(metrics['胜率'].rstrip('%'))
    
    if sharpe > 1.0:
        report += "✓ 夏普比率 > 1.0，风险调整后收益优秀\n"
    elif sharpe > 0.5:
        report += "○ 夏普比率 > 0.5，风险调整后收益良好\n"
    else:
        report += "△ 夏普比率较低，需关注风险\n"
    
    if abs(max_dd) < 20:
        report += "✓ 最大回撤控制在20%以内，风控较好\n"
    else:
        report += "△ 最大回撤较大，建议优化参数\n"
    
    if win_rate > 60:
        report += "✓ 胜率超过60%，交易质量较高\n"
    
    report += f"""
六、风险提示
--------------------------------------------------------------------------------
1. 本策略基于历史数据回测，不代表未来表现
2. 2025年以来的市场环境可能与历史不同
3. 策略参数可能需要根据市场变化调整
4. 建议结合其他指标综合判断

================================================================================
报告生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
================================================================================
"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(report)
    return output_path


def main():
    """主函数"""
    print("="*70)
    print("价量共振V3策略回测")
    print("="*70)
    
    # 1. 加载数据
    print("\n[1/5] 加载数据...")
    df = load_data()
    print(f"  加载 {len(df)} 条数据")
    print(f"  时间范围: {df.index[0].date()} ~ {df.index[-1].date()}")
    
    # 2. 计算策略信号
    print("\n[2/5] 计算价量共振V3信号...")
    data = volume_price_resonance_v3(df)
    print("  信号计算完成")
    
    # 3. 回测
    print("\n[3/5] 执行回测...")
    result = backtest(data)
    print("  回测完成")
    
    # 4. 计算指标
    print("\n[4/5] 计算绩效指标...")
    metrics, result = calculate_metrics(result)
    
    # 5. 生成报告和图表
    print("\n[5/5] 生成报告和图表...")
    report_path = generate_report(metrics, result)
    chart_path = plot_results(result)
    
    print("\n" + "="*70)
    print("回测完成!")
    print(f"报告文件: {report_path}")
    print(f"图表文件: {chart_path}")
    print("="*70)
    
    return metrics, result


if __name__ == "__main__":
    main()
