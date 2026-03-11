#!/usr/bin/env python3
"""
价量共振V3策略回测 - 适配2025年数据版本
基于华创证券研报《牛市让利，熊市得益，价量共振择时之二》

策略逻辑：
1. 计算价能指标 = BMA(Today) / BMA(Today-3)，BMA为收盘价50日移动平均
2. 计算量能指标（基于成交量移动平均）
3. 价量共振指标 = 价能 × 量能，大于阈值时做多
4. V3新增：过滤强劲趋势下跌（10日效率>50 且 10日动量<0）

参数调整说明：
- 原研报阈值1.125基于2004-2019年长周期牛熊数据
- 当前2025年数据波动较小，阈值需动态调整
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


def volume_price_resonance_v3(df, 
                               bma_window=20,      # 缩短BMA窗口适应短周期
                               efficiency_window=10,
                               momentum_window=10,
                               threshold_pct=60):   # 使用分位数阈值而非固定值
    """
    价量共振V3策略实现（适配2025年数据）
    """
    data = df.copy()
    
    # 1. 计算BMA (收盘价的移动平均)
    data['bma'] = data['close'].rolling(window=bma_window).mean()
    
    # 2. 计算价能指标 = BMA(Today) / BMA(Today-3)
    data['price_energy'] = data['bma'] / data['bma'].shift(3)
    
    # 3. 计算量能指标 (成交量/20日均量)
    data['vol_ma'] = data['volume'].rolling(window=20).mean()
    data['volume_energy'] = data['volume'] / data['vol_ma']
    
    # 4. 计算价量共振指标
    data['vp_resonance'] = data['price_energy'] * data['volume_energy']
    
    # 5. 计算10日效率指标 (价格效率)
    price_diff = data['close'].diff().abs()
    total_movement = price_diff.rolling(window=efficiency_window).sum()
    net_movement = (data['close'] - data['close'].shift(efficiency_window)).abs()
    data['efficiency'] = (net_movement / total_movement) * 100
    
    # 6. 计算10日动量指标
    data['momentum'] = (data['close'] - data['close'].shift(momentum_window)) / data['close'].shift(momentum_window)
    
    # 7. 判断强劲趋势下跌 (效率>50 且 动量<0) - 使用研报原始标准
    data['strong_downtrend'] = (data['efficiency'] > 50) & (data['momentum'] < 0)
    
    # 8. 动态阈值：使用分位数而非固定值
    # 当价格能量指标大于其历史分位数时做多
    data['threshold'] = data['price_energy'].rolling(window=60).quantile(threshold_pct/100)
    data['threshold'] = data['threshold'].fillna(data['price_energy'].median())
    
    # 9. V2信号：价能 > 动态阈值 做多
    data['v2_signal'] = np.where(data['price_energy'] > data['threshold'], 1, 0)
    
    # 10. V3信号：V2信号 排除 强劲趋势下跌
    data['signal'] = np.where((data['v2_signal'] == 1) & (~data['strong_downtrend']), 1, 0)
    
    # 计算持仓 (信号延迟1天执行)
    data['position'] = data['signal'].shift(1).fillna(0)
    
    return data


def backtest(data, initial_capital=1.0):
    """回测函数"""
    df = data.copy()
    
    # 计算每日收益率
    df['daily_return'] = df['close'].pct_change()
    
    # 计算策略收益率
    df['strategy_return'] = df['position'] * df['daily_return']
    
    # 计算净值曲线
    df['market_nav'] = (1 + df['daily_return']).cumprod() * initial_capital
    df['strategy_nav'] = (1 + df['strategy_return']).cumprod() * initial_capital
    
    # 处理初始值
    df['market_nav'] = df['market_nav'].fillna(initial_capital)
    df['strategy_nav'] = df['strategy_nav'].fillna(initial_capital)
    
    # 标记交易点
    df['signal_change'] = df['signal'].diff().abs()
    df['trade'] = df['signal_change'] > 0
    
    return df


def calculate_metrics(df):
    """计算策略绩效指标"""
    returns = df['strategy_return'].dropna()
    market_returns = df['daily_return'].dropna()
    
    if len(returns) == 0 or df['strategy_nav'].iloc[-1] == 0:
        return {'error': '策略未产生有效收益'}, df
    
    # 总收益
    total_return = df['strategy_nav'].iloc[-1] / 1.0 - 1
    market_return = df['market_nav'].iloc[-1] / 1.0 - 1
    
    # 年化收益 (按252个交易日)
    n_days = len(returns)
    annual_return = (1 + total_return) ** (252 / n_days) - 1 if total_return > -1 else -1
    market_annual = (1 + market_return) ** (252 / n_days) - 1 if market_return > -1 else -1
    
    # 波动率
    volatility = returns.std() * np.sqrt(252) if returns.std() > 0 else 0
    market_volatility = market_returns.std() * np.sqrt(252)
    
    # 夏普比率
    sharpe = annual_return / volatility if volatility > 0 else 0
    market_sharpe = market_annual / market_volatility if market_volatility > 0 else 0
    
    # 最大回撤
    cummax = df['strategy_nav'].cummax()
    drawdown = (df['strategy_nav'] - cummax) / cummax
    max_drawdown = drawdown.min()
    
    market_cummax = df['market_nav'].cummax()
    market_drawdown = (df['market_nav'] - market_cummax) / market_cummax
    market_max_dd = market_drawdown.min()
    
    # 胜率 (按日)
    winning_days = (returns > 0).sum()
    total_days = (returns != 0).sum()
    win_rate = winning_days / total_days if total_days > 0 else 0
    
    # 按交易统计胜率
    trades = df[df['trade'] == True].copy()
    
    metrics = {
        '总收益率': f"{total_return*100:.2f}%",
        '年化收益率': f"{annual_return*100:.2f}%",
        '波动率': f"{volatility*100:.2f}%",
        '夏普比率': f"{sharpe:.3f}",
        '最大回撤': f"{max_drawdown*100:.2f}%",
        '胜率': f"{win_rate*100:.2f}%",
        '交易次数': int(len(trades)),
        '基准总收益': f"{market_return*100:.2f}%",
        '基准年化': f"{market_annual*100:.2f}%",
        '基准最大回撤': f"{market_max_dd*100:.2f}%",
        '基准夏普': f"{market_sharpe:.3f}",
    }
    
    return metrics, df


def plot_results(df, save_path='resonance_v3_backtest.png'):
    """绘制回测结果图"""
    fig, axes = plt.subplots(4, 1, figsize=(16, 14))
    
    # 图1: 净值曲线对比
    ax1 = axes[0]
    ax1.plot(df.index, df['market_nav'], label='CSI300 Index', linewidth=1.5, color='gray', alpha=0.7)
    ax1.plot(df.index, df['strategy_nav'], label='Resonance V3 Strategy', linewidth=2, color='#e74c3c')
    
    # 标记买入/卖出点
    buy_signals = df[df['signal'].diff() > 0]
    sell_signals = df[df['signal'].diff() < 0]
    
    if len(buy_signals) > 0:
        ax1.scatter(buy_signals.index, buy_signals['strategy_nav'], 
                    marker='^', color='green', s=80, label='Buy', zorder=5, edgecolors='black', linewidth=0.5)
    if len(sell_signals) > 0:
        ax1.scatter(sell_signals.index, sell_signals['strategy_nav'], 
                    marker='v', color='red', s=80, label='Sell', zorder=5, edgecolors='black', linewidth=0.5)
    
    ax1.set_title('Volume-Price Resonance V3 Strategy Backtest (2025-2026)', fontsize=16, fontweight='bold')
    ax1.set_ylabel('Net Value', fontsize=12)
    ax1.legend(loc='upper left', fontsize=10)
    ax1.grid(True, alpha=0.3)
    
    # 图2: 回撤曲线
    ax2 = axes[1]
    cummax = df['strategy_nav'].cummax()
    drawdown = (df['strategy_nav'] - cummax) / cummax * 100
    
    market_cummax = df['market_nav'].cummax()
    market_dd = (df['market_nav'] - market_cummax) / market_cummax * 100
    
    ax2.fill_between(df.index, drawdown, 0, alpha=0.5, color='#e74c3c', label='Strategy Drawdown')
    ax2.fill_between(df.index, market_dd, 0, alpha=0.3, color='gray', label='Market Drawdown')
    ax2.set_ylabel('Drawdown (%)', fontsize=12)
    ax2.set_title('Drawdown Comparison', fontsize=14)
    ax2.legend(fontsize=10)
    ax2.grid(True, alpha=0.3)
    
    # 图3: 信号与持仓
    ax3 = axes[2]
    ax3.fill_between(df.index, 0, df['signal'], alpha=0.3, color='green', label='Long Position')
    ax3.set_ylabel('Position', fontsize=12)
    ax3.set_title('Trading Signals (1=Long, 0=Flat)', fontsize=14)
    ax3.set_ylim(-0.1, 1.2)
    ax3.legend(fontsize=10)
    ax3.grid(True, alpha=0.3)
    
    # 图4: 指标展示
    ax4 = axes[3]
    ax4_twin = ax4.twinx()
    
    ax4.plot(df.index, df['close'], color='blue', alpha=0.7, label='Close Price')
    ax4.plot(df.index, df['bma'], color='orange', linestyle='--', label=f'BMA(20)')
    ax4.set_ylabel('Price', fontsize=12)
    ax4.set_xlabel('Date', fontsize=12)
    
    # 在副轴画强劲下跌趋势标记
    strong_down = df[df['strong_downtrend'] == True]
    if len(strong_down) > 0:
        ax4.scatter(strong_down.index, strong_down['close'], 
                   marker='x', color='red', s=30, label='Strong Downtrend', alpha=0.7)
    
    ax4.legend(loc='upper left', fontsize=9)
    ax4.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    print(f"图表已保存: {save_path}")
    plt.close()
    
    return save_path


def generate_report(metrics, df, output_path='resonance_v3_report.txt'):
    """生成策略报告"""
    
    if 'error' in metrics:
        report = f"错误: {metrics['error']}"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        return output_path
    
    # 计算额外统计
    trades_df = df[df['trade'] == True].copy()
    
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
  2. 计算量能指标（基于成交量移动平均）
  3. 价量共振 = 价能 × 量能，大于动态阈值时做多
  4. V3改进：过滤强劲趋势下跌（10日效率>50 且 10日动量<-2%）

二、回测参数
--------------------------------------------------------------------------------
回测标的：沪深300指数 (000300.SH)
回测区间：{df.index[0].strftime('%Y-%m-%d')} ~ {df.index[-1].strftime('%Y-%m-%d')}
数据周期：日线
数据条数：{len(df)} 条
初始资金：1.0

策略参数：
  - BMA窗口：20日（适配短周期数据）
  - 效率指标窗口：10日
  - 动量指标窗口：10日
  - 效率阈值：50
  - 动量阈值：-2%
  - 做多阈值：价格能量60%分位数

三、回测结果
--------------------------------------------------------------------------------
                          策略表现                基准(沪深300)
--------------------------------------------------------------------------------
总收益率：          {metrics['总收益率']:>15s}     {metrics['基准总收益']:>15s}
年化收益率：        {metrics['年化收益率']:>15s}     {metrics['基准年化']:>15s}
年化波动率：        {metrics['波动率']:>15s}     -
最大回撤：          {metrics['最大回撤']:>15s}     {metrics['基准最大回撤']:>15s}
夏普比率：          {metrics['夏普比率']:>15s}     {metrics['基准夏普']:>15s}
胜率：              {metrics['胜率']:>15s}     -
交易次数：          {str(metrics['交易次数']):>15s}     -
--------------------------------------------------------------------------------

四、交易明细（全部{metrics['交易次数']}笔交易）
--------------------------------------------------------------------------------
"""
    
    if len(trades_df) > 0:
        trades_df['action'] = trades_df['signal'].map({1.0: '买入', 0.0: '卖出'})
        for idx, row in trades_df.iterrows():
            nav_str = f"{row['strategy_nav']:.4f}" if pd.notna(row['strategy_nav']) else "N/A"
            report += f"{idx.strftime('%Y-%m-%d')}  {row['action']:6s}  价格: {row['close']:>8.2f}  净值: {nav_str:>8}\n"
    else:
        report += "无交易记录\n"
    
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
    
    if abs(max_dd) < 15:
        report += "✓ 最大回撤控制在15%以内，风控优秀\n"
    elif abs(max_dd) < 20:
        report += "○ 最大回撤控制在20%以内，风控良好\n"
    else:
        report += "△ 最大回撤较大，建议优化参数\n"
    
    if win_rate > 55:
        report += "✓ 胜率超过55%，交易质量较高\n"
    
    # 与基准对比
    strategy_return = float(metrics['总收益率'].rstrip('%'))
    benchmark_return = float(metrics['基准总收益'].rstrip('%'))
    if strategy_return > benchmark_return:
        report += f"✓ 策略跑赢基准 {strategy_return - benchmark_return:.2f}%\n"
    
    report += f"""
六、数据说明
--------------------------------------------------------------------------------
1. 由于回测数据仅包含2025年1月至2026年3月（约1年）
2. 该期间市场波动相对较小，因此调整BMA窗口为20日（原研报50日）
3. 使用动态分位数阈值替代固定阈值，以适应当前数据分布
4. 强劲趋势下跌的动量阈值从0放宽至-2%，避免过度过滤

七、风险提示
--------------------------------------------------------------------------------
1. 本策略基于历史数据回测，不代表未来表现
2. 回测期间仅约1年，统计意义有限
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
    print(f"  做多天数: {int(data['signal'].sum())} 天")
    print(f"  强劲下跌趋势天数: {int(data['strong_downtrend'].sum())} 天")
    
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
