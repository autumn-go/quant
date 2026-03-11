#!/usr/bin/env python3
"""
双剑合璧V3策略回测
基于研报《涨跌停剪刀差择时系列之四：权衡利弊，推波助澜V3》

策略逻辑：
1. 价量共振V3：效率指标+动量指标过滤强劲趋势下跌
2. 推波助澜：涨跌停比率剪刀差（基于等权，因缺少市值数据）
3. 双剑合璧信号 = 推波助澜信号 OR 价量共振信号
"""

import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'SimHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

DB_PATH = '/root/.openclaw/workspace/quant-main/data-collector/csi300_data.db'


def load_data():
    """加载沪深300指数和涨跌停数据"""
    conn = sqlite3.connect(DB_PATH)
    
    # 读取指数日线数据
    df_index = pd.read_sql_query('''
        SELECT date, open, high, low, close, volume, amount
        FROM csi300_index_daily
        ORDER BY date
    ''', conn)
    
    # 读取涨跌停数据 - 按日期统计
    df_limit = pd.read_sql_query('''
        SELECT date, limit_type, COUNT(*) as count
        FROM limit_up_down
        GROUP BY date, limit_type
    ''', conn)
    
    conn.close()
    
    # 处理日期
    df_index['date'] = pd.to_datetime(df_index['date'])
    df_index.set_index('date', inplace=True)
    df_index.sort_index(inplace=True)
    
    df_limit['date'] = pd.to_datetime(df_limit['date'])
    df_limit_pivot = df_limit.pivot(index='date', columns='limit_type', values='count').fillna(0)
    
    # 合并数据
    df = df_index.join(df_limit_pivot, how='left')
    df['up'] = df.get('up', 0)
    df['down'] = df.get('down', 0)
    
    return df


def calculate_price_volume_resonance_v3(df, bma_window=20, efficiency_window=10, momentum_window=10):
    """
    价量共振V3策略
    """
    data = df.copy()
    
    # 计算BMA
    data['bma'] = data['close'].rolling(window=bma_window).mean()
    
    # 价能指标
    data['price_energy'] = data['bma'] / data['bma'].shift(3)
    
    # 量能指标
    data['vol_ma'] = data['volume'].rolling(window=20).mean()
    data['volume_energy'] = data['volume'] / data['vol_ma']
    
    # 效率指标
    price_diff = data['close'].diff().abs()
    total_movement = price_diff.rolling(window=efficiency_window).sum()
    net_movement = (data['close'] - data['close'].shift(efficiency_window)).abs()
    data['efficiency'] = (net_movement / total_movement) * 100
    
    # 动量指标
    data['momentum'] = (data['close'] - data['close'].shift(momentum_window)) / data['close'].shift(momentum_window)
    
    # 强劲趋势下跌
    data['strong_downtrend'] = (data['efficiency'] > 50) & (data['momentum'] < 0)
    
    # 动态阈值
    data['threshold'] = data['price_energy'].rolling(window=60).quantile(0.6)
    data['threshold'] = data['threshold'].fillna(data['price_energy'].median())
    
    # 基础信号
    data['pv_v2_signal'] = np.where(data['price_energy'] > data['threshold'], 1, 0)
    
    # V3信号（过滤强劲下跌）
    data['pv_signal'] = np.where((data['pv_v2_signal'] == 1) & (~data['strong_downtrend']), 1, 0)
    
    return data


def calculate_tuibo_zhulan(df, ama_short=30, ama_long=100):
    """
    推波助澜策略（基于涨跌停剪刀差）
    注：使用等权计算，因缺少自由流通市值数据
    """
    data = df.copy()
    
    # 计算涨跌停比率剪刀差
    total_stocks = 300  # 沪深300成分股数量
    data['up_ratio'] = data['up'] / total_stocks
    data['down_ratio'] = data['down'] / total_stocks
    data['scissors_diff'] = data['up_ratio'] - data['down_ratio']
    
    # 计算AMA（自适应移动平均）- 使用EMA近似
    data['ama_short'] = data['scissors_diff'].ewm(span=ama_short, adjust=False).mean()
    data['ama_long'] = data['scissors_diff'].ewm(span=ama_long, adjust=False).mean()
    
    # 推波助澜信号
    # 条件1: AMA_short / AMA_long > 1.15
    # 条件2: AMA_short > 0 且 AMA_long > 0
    data['ama_ratio'] = data['ama_short'] / data['ama_long']
    data['tb_signal'] = np.where(
        (data['ama_ratio'] > 1.15) & 
        (data['ama_short'] > 0) & 
        (data['ama_long'] > 0), 1, 0
    )
    
    return data


def double_sword_v3(df):
    """
    双剑合璧V3策略
    信号 = 推波助澜信号 OR 价量共振信号
    """
    data = df.copy()
    
    # 计算两个子策略
    data = calculate_price_volume_resonance_v3(data)
    data = calculate_tuibo_zhulan(data)
    
    # 双剑合璧信号 - "或"逻辑
    data['ds_signal'] = np.where((data['tb_signal'] == 1) | (data['pv_signal'] == 1), 1, 0)
    
    # 持仓（延迟1天执行）
    data['position'] = data['ds_signal'].shift(1).fillna(0)
    
    return data


def backtest(data, initial_capital=1.0):
    """回测"""
    df = data.copy()
    
    # 计算收益率
    df['daily_return'] = df['close'].pct_change()
    df['strategy_return'] = df['position'] * df['daily_return']
    
    # 净值曲线
    df['market_nav'] = (1 + df['daily_return']).cumprod() * initial_capital
    df['strategy_nav'] = (1 + df['strategy_return']).cumprod() * initial_capital
    
    # 填充初始值
    df['market_nav'] = df['market_nav'].fillna(initial_capital)
    df['strategy_nav'] = df['strategy_nav'].fillna(initial_capital)
    
    # 标记交易
    df['signal_change'] = df['ds_signal'].diff().abs()
    df['trade'] = df['signal_change'] > 0
    
    return df


def calculate_metrics(df):
    """计算绩效指标"""
    returns = df['strategy_return'].dropna()
    market_returns = df['daily_return'].dropna()
    
    # 总收益
    total_return = df['strategy_nav'].iloc[-1] / 1.0 - 1
    market_return = df['market_nav'].iloc[-1] / 1.0 - 1
    
    # 年化收益
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
    market_dd = (df['market_nav'] - market_cummax) / market_cummax
    market_max_dd = market_dd.min()
    
    # 胜率
    winning_days = (returns > 0).sum()
    total_days = (returns != 0).sum()
    win_rate = winning_days / total_days if total_days > 0 else 0
    
    # 交易次数
    trades = df[df['trade'] == True].copy()
    
    # 盈亏比
    avg_gain = returns[returns > 0].mean() if (returns > 0).any() else 0
    avg_loss = abs(returns[returns < 0].mean()) if (returns < 0).any() else 1
    profit_loss_ratio = avg_gain / avg_loss if avg_loss > 0 else 0
    
    metrics = {
        '总收益率': f"{total_return*100:.2f}%",
        '年化收益率': f"{annual_return*100:.2f}%",
        '波动率': f"{volatility*100:.2f}%",
        '夏普比率': f"{sharpe:.3f}",
        '最大回撤': f"{max_drawdown*100:.2f}%",
        '胜率': f"{win_rate*100:.2f}%",
        '盈亏比': f"{profit_loss_ratio:.2f}",
        '交易次数': int(len(trades)),
        '基准总收益': f"{market_return*100:.2f}%",
        '基准年化': f"{market_annual*100:.2f}%",
        '基准最大回撤': f"{market_max_dd*100:.2f}%",
        '基准夏普': f"{market_sharpe:.3f}",
    }
    
    return metrics


def plot_results(df, save_path='double_sword_v3_backtest.png'):
    """绘制回测图表"""
    fig, axes = plt.subplots(5, 1, figsize=(16, 18))
    
    # 图1: 净值曲线
    ax1 = axes[0]
    ax1.plot(df.index, df['market_nav'], label='CSI300 Index', linewidth=1.5, color='gray', alpha=0.7)
    ax1.plot(df.index, df['strategy_nav'], label='Double Sword V3', linewidth=2, color='#e74c3c')
    
    buy_signals = df[df['ds_signal'].diff() > 0]
    sell_signals = df[df['ds_signal'].diff() < 0]
    
    if len(buy_signals) > 0:
        ax1.scatter(buy_signals.index, buy_signals['strategy_nav'], 
                   marker='^', color='green', s=60, label='Buy', zorder=5)
    if len(sell_signals) > 0:
        ax1.scatter(sell_signals.index, sell_signals['strategy_nav'], 
                   marker='v', color='red', s=60, label='Sell', zorder=5)
    
    ax1.set_title('Double Sword V3 Strategy Backtest (2024-2026)', fontsize=16, fontweight='bold')
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
    
    # 图3: 各策略信号
    ax3 = axes[2]
    ax3.fill_between(df.index, 0, df['tb_signal'], alpha=0.3, color='blue', label='Tuibo')
    ax3.fill_between(df.index, 0, df['pv_signal'], alpha=0.3, color='orange', label='PV Resonance')
    ax3.fill_between(df.index, 0, df['ds_signal'], alpha=0.5, color='green', label='Double Sword')
    ax3.set_ylabel('Signal')
    ax3.set_title('Strategy Signals (Tuibo OR PV)')
    ax3.set_ylim(-0.1, 1.2)
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    
    # 图4: 推波助澜比率
    ax4 = axes[3]
    ax4.plot(df.index, df['scissors_diff'], label='Scissors Diff', color='purple', alpha=0.7)
    ax4.plot(df.index, df['ama_short'], label='AMA30', color='blue')
    ax4.plot(df.index, df['ama_long'], label='AMA100', color='red')
    ax4.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    ax4.set_ylabel('Ratio')
    ax4.set_title('Tuibo Zhulan Indicators')
    ax4.legend()
    ax4.grid(True, alpha=0.3)
    
    # 图5: 价量共振指标
    ax5 = axes[4]
    ax5.plot(df.index, df['close'], label='Close', color='black', alpha=0.7)
    ax5.plot(df.index, df['bma'], label='BMA20', color='orange', linestyle='--')
    ax5_twin = ax5.twinx()
    ax5_twin.plot(df.index, df['efficiency'], label='Efficiency', color='blue', alpha=0.5)
    ax5_twin.axhline(y=50, color='red', linestyle='--', alpha=0.5)
    ax5.set_ylabel('Price')
    ax5_twin.set_ylabel('Efficiency')
    ax5.set_xlabel('Date')
    ax5.set_title('Price-Volume Resonance Indicators')
    ax5.legend(loc='upper left')
    ax5_twin.legend(loc='upper right')
    ax5.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    print(f"图表已保存: {save_path}")
    plt.close()


def generate_report(metrics, df, output_path='double_sword_v3_report.txt'):
    """生成策略报告"""
    trades_df = df[df['trade'] == True].copy()
    
    report = f"""
================================================================================
                    双剑合璧V3策略回测报告
            Double Sword V3: Tuibo V3 + Price-Volume Resonance V3
================================================================================

一、策略概述
--------------------------------------------------------------------------------
策略来源：华创证券涨跌停剪刀差择时系列

子策略1 - 推波助澜V3：
  - 基于涨跌停比率剪刀差（涨停比率 - 跌停比率）
  - AMA30 / AMA100 > 1.15 且 AMA30 > 0 且 AMA100 > 0 时做多
  - 注：因数据限制，使用等权计算（原研报为市值加权）

子策略2 - 价量共振V3：
  - 价能指标 = BMA(Today) / BMA(Today-3)
  - 效率指标 + 动量指标过滤强劲趋势下跌
  - 价格能量 > 60%分位数 且 非强劲下跌 时做多

双剑合璧信号：
  信号 = 推波助澜信号 OR 价量共振信号
  （任一子策略看多即做多，双重机会捕捉）

二、回测参数
--------------------------------------------------------------------------------
回测标的：沪深300指数 (000300.SH)
回测区间：{df.index[0].strftime('%Y-%m-%d')} ~ {df.index[-1].strftime('%Y-%m-%d')}
数据周期：日线
初始资金：1.0

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
盈亏比：            {metrics['盈亏比']:>15s}     -
交易次数：          {str(metrics['交易次数']):>15s}     -
--------------------------------------------------------------------------------

四、交易明细（最近15笔）
--------------------------------------------------------------------------------
"""
    
    if len(trades_df) > 0:
        trades_df['action'] = trades_df['ds_signal'].map({1.0: '买入', 0.0: '卖出'})
        recent_trades = trades_df.tail(15)
        for idx, row in recent_trades.iterrows():
            report += f"{idx.strftime('%Y-%m-%d')}  {row['action']:6s}  价格: {row['close']:>8.2f}  净值: {row['strategy_nav']:.4f}\n"
    
    # 子策略信号统计
    tb_days = int(df['tb_signal'].sum())
    pv_days = int(df['pv_signal'].sum())
    ds_days = int(df['ds_signal'].sum())
    
    report += f"""
--------------------------------------------------------------------------------

五、子策略信号统计
--------------------------------------------------------------------------------
推波助澜做多天数：    {tb_days} 天
价量共振做多天数：    {pv_days} 天
双剑合璧做多天数：    {ds_days} 天

六、策略评价
--------------------------------------------------------------------------------
"""
    
    sharpe = float(metrics['夏普比率'])
    max_dd = float(metrics['最大回撤'].rstrip('%'))
    win_rate = float(metrics['胜率'].rstrip('%'))
    
    if sharpe > 1.0:
        report += "✓ 夏普比率 > 1.0，风险调整后收益优秀\n"
    elif sharpe > 0.5:
        report += "○ 夏普比率 > 0.5，风险调整后收益良好\n"
    
    if abs(max_dd) < 15:
        report += "✓ 最大回撤控制在15%以内，风控优秀\n"
    elif abs(max_dd) < 20:
        report += "○ 最大回撤控制在20%以内，风控良好\n"
    
    if win_rate > 55:
        report += "✓ 胜率超过55%，交易质量较高\n"
    
    strategy_return = float(metrics['总收益率'].rstrip('%'))
    benchmark_return = float(metrics['基准总收益'].rstrip('%'))
    if strategy_return > benchmark_return:
        report += f"✓ 策略跑赢基准 {strategy_return - benchmark_return:.2f}%\n"
    
    report += f"""
七、风险提示
--------------------------------------------------------------------------------
1. 本策略基于历史数据回测，不代表未来表现
2. 推波助澜V3因缺少自由流通市值数据，使用等权计算替代
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
    print("双剑合璧V3策略回测")
    print("Double Sword V3: Tuibo V3 + Price-Volume Resonance V3")
    print("="*70)
    
    # 1. 加载数据
    print("\n[1/5] 加载数据...")
    df = load_data()
    print(f"  加载 {len(df)} 条数据")
    print(f"  时间范围: {df.index[0].date()} ~ {df.index[-1].date()}")
    
    # 2. 计算双剑合璧信号
    print("\n[2/5] 计算双剑合璧V3信号...")
    data = double_sword_v3(df)
    print(f"  推波助澜做多: {int(data['tb_signal'].sum())} 天")
    print(f"  价量共振做多: {int(data['pv_signal'].sum())} 天")
    print(f"  双剑合璧做多: {int(data['ds_signal'].sum())} 天")
    
    # 3. 回测
    print("\n[3/5] 执行回测...")
    result = backtest(data)
    
    # 4. 计算指标
    print("\n[4/5] 计算绩效指标...")
    metrics = calculate_metrics(result)
    
    # 5. 生成报告和图表
    print("\n[5/5] 生成报告和图表...")
    report_path = generate_report(metrics, result)
    chart_path = plot_results(result)
    
    print("\n" + "="*70)
    print("回测完成!")
    print(f"报告文件: {report_path}")
    print(f"图表文件: {chart_path}")
    print("="*70)


if __name__ == "__main__":
    main()
