#!/usr/bin/env python3
"""
双剑合璧V3 Final - 周期自适应 + 阈值自适应版本

优化汇总:
1. 周期自适应: 根据ADX趋势强度动态调整AMA周期
   - 强趋势(ADX>40): 用长周期 (减少假信号)
   - 震荡(ADX<20): 用短周期 (快速响应)
   
2. 阈值自适应: 分位数自适应 (AMA比率的70%分位数)
   - 牛市阈值自动上移, 熊市自动下移
   
3. 基础配置: AMA15/40, 分位数阈值

参考: 华创证券《涨跌停剪刀差择时系列之四》
"""

import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'SimHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

DB_PATH = '/root/.openclaw/workspace/quant-main/data-collector/csi300_data.db'


# ============================================================
# 数据加载
# ============================================================

def load_data():
    """加载沪深300指数和涨跌停数据"""
    conn = sqlite3.connect(DB_PATH)
    
    df_index = pd.read_sql_query('''
        SELECT date, open, high, low, close, volume, amount
        FROM csi300_index_daily ORDER BY date
    ''', conn)
    df_index['date'] = pd.to_datetime(df_index['date'])
    df_index.set_index('date', inplace=True)
    df_index.sort_index(inplace=True)
    
    df_limit = pd.read_sql_query('''
        SELECT date, limit_type, COUNT(*) as count
        FROM limit_up_down GROUP BY date, limit_type
    ''', conn)
    df_limit['date'] = pd.to_datetime(df_limit['date'])
    df_limit_pivot = df_limit.pivot(index='date', columns='limit_type', values='count').fillna(0)
    
    conn.close()
    
    df = df_index.copy()
    df['up'] = df_limit_pivot.get('up', 0)
    df['down'] = df_limit_pivot.get('down', 0)
    return df


# ============================================================
# 核心指标计算
# ============================================================

def calculate_price_volume_resonance_v3(df, bma_window=20, efficiency_window=10, 
                                         momentum_window=10):
    """
    价量共振V3策略
    - 价能指标: BMA(Today) / BMA(Today-3)
    - 效率指标 + 动量指标过滤强劲趋势下跌
    """
    data = df.copy()
    
    # BMA
    data['bma'] = data['close'].rolling(window=bma_window).mean()
    data['price_energy'] = data['bma'] / data['bma'].shift(3)
    
    # 量能
    data['vol_ma'] = data['volume'].rolling(window=20).mean()
    data['volume_energy'] = data['volume'] / data['vol_ma']
    
    # 效率指标
    price_diff = data['close'].diff().abs()
    total_movement = price_diff.rolling(window=efficiency_window).sum()
    net_movement = (data['close'] - data['close'].shift(efficiency_window)).abs()
    data['efficiency'] = (net_movement / total_movement.replace(0, np.nan)) * 100
    
    # 动量指标
    data['momentum'] = (data['close'] - data['close'].shift(momentum_window)) / data['close'].shift(momentum_window)
    
    # 强劲趋势下跌
    data['strong_downtrend'] = (data['efficiency'] > 50) & (data['momentum'] < 0)
    
    # 动态阈值 (60%分位数)
    data['threshold'] = data['price_energy'].rolling(window=60).quantile(0.6)
    data['threshold'] = data['threshold'].fillna(data['price_energy'].median())
    
    # 基础信号
    data['pv_v2_signal'] = np.where(data['price_energy'] > data['threshold'], 1, 0)
    
    # V3信号（过滤强劲下跌）
    data['pv_signal'] = np.where((data['pv_v2_signal'] == 1) & (~data['strong_downtrend']), 1, 0)
    
    return data


def calculate_adx(df, window=14):
    """
    计算ADX (平均趋向指数) - 趋势强度指标
    返回 0~100，越高表示趋势越强
    """
    data = df.copy()
    
    # +DM / -DM
    data['plus_dm'] = np.where(
        (data['high'] - data['high'].shift(1)) > (data['low'].shift(1) - data['low']),
        np.maximum(data['high'] - data['high'].shift(1), 0), 0
    )
    data['minus_dm'] = np.where(
        (data['low'].shift(1) - data['low']) > (data['high'] - data['high'].shift(1)),
        np.maximum(data['low'].shift(1) - data['low'], 0), 0
    )
    
    # TR (真实波幅)
    high_low = data['high'] - data['low']
    high_close = (data['high'] - data['close'].shift()).abs()
    low_close = (data['low'] - data['close'].shift()).abs()
    data['tr'] = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    
    # ATR
    data['atr'] = data['tr'].rolling(window).mean()
    
    # +DI / -DI
    data['plus_di'] = 100 * data['plus_dm'].rolling(window).mean() / data['atr']
    data['minus_di'] = 100 * data['minus_dm'].rolling(window).mean() / data['atr']
    
    # DX
    data['dx'] = 100 * (data['plus_di'] - data['minus_di']).abs() / (data['plus_di'] + data['minus_di'])
    
    # ADX
    data['adx'] = data['dx'].rolling(window).mean()
    
    return data['adx'].fillna(25)


def get_adaptive_periods(adx, base_short=15, base_long=40):
    """
    根据ADX趋势强度动态调整周期
    
    ADX > 40: 强趋势 → 用长周期 (减少假信号)
    ADX 20-40: 中等 → 用中等周期
    ADX < 20: 震荡 → 用短周期 (快速响应)
    """
    # 趋势强度系数 (0.6 ~ 1.4)
    trend_factor = np.clip(adx / 30, 0.6, 1.4)
    
    # 周期调整
    adaptive_short = (base_short * trend_factor).round().astype(int)
    adaptive_long = (base_long * trend_factor).round().astype(int)
    
    return adaptive_short, adaptive_long


def calculate_tuibo_zhulan_adaptive(df, base_short=15, base_long=40, 
                                     threshold_quantile=0.7, adx_window=20):
    """
    推波助澜 - 周期自适应 + 阈值自适应版本
    
    周期自适应: 根据ADX动态调整
    阈值自适应: 使用滚动分位数
    """
    data = df.copy()
    
    # 计算涨跌停剪刀差
    total_stocks = 300
    data['up_ratio'] = data['up'] / total_stocks
    data['down_ratio'] = data['down'] / total_stocks
    data['scissors_diff'] = data['up_ratio'] - data['down_ratio']
    
    # 计算ADX趋势强度
    data['adx'] = calculate_adx(data, adx_window)
    
    # 获取自适应周期
    data['ama_short_period'], data['ama_long_period'] = get_adaptive_periods(
        data['adx'], base_short, base_long)
    
    # 逐行计算AMA (因为周期变化)
    data['ama_short'] = np.nan
    data['ama_long'] = np.nan
    
    for i in range(len(data)):
        if i < 5:
            continue
        short_span = int(data.iloc[i]['ama_short_period'])
        long_span = int(data.iloc[i]['ama_long_period'])
        
        series = data['scissors_diff'].iloc[:i+1]
        if len(series) >= short_span:
            data.iloc[i, data.columns.get_loc('ama_short')] = series.ewm(span=short_span).mean().iloc[-1]
        if len(series) >= long_span:
            data.iloc[i, data.columns.get_loc('ama_long')] = series.ewm(span=long_span).mean().iloc[-1]
    
    data['ama_short'] = data['ama_short'].ffill()
    data['ama_long'] = data['ama_long'].ffill()
    
    # AMA比率
    data['ama_ratio'] = data['ama_short'] / data['ama_long'].replace(0, np.nan)
    
    # 阈值自适应: 滚动分位数
    data['adaptive_threshold'] = data['ama_ratio'].rolling(60).quantile(threshold_quantile)
    data['adaptive_threshold'] = data['adaptive_threshold'].fillna(data['ama_ratio'].median())
    
    # 推波助澜信号
    data['tb_signal'] = np.where(
        (data['ama_ratio'] > data['adaptive_threshold']) & 
        (data['ama_short'] > 0) & 
        (data['ama_long'] > 0), 1, 0
    )
    
    return data


def double_sword_v3_final(df):
    """
    双剑合璧V3 Final
    信号 = 推波助澜(周期自适应+阈值自适应) OR 价量共振
    """
    data = df.copy()
    
    # 计算两个子策略
    data = calculate_price_volume_resonance_v3(data)
    data = calculate_tuibo_zhulan_adaptive(data)
    
    # 双剑合璧信号
    data['ds_signal'] = np.where((data['tb_signal'] == 1) | (data['pv_signal'] == 1), 1, 0)
    
    # 持仓（延迟1天执行）
    data['position'] = data['ds_signal'].shift(1).fillna(0)
    
    return data


# ============================================================
# 回测与评估
# ============================================================

def backtest(data, initial_capital=1.0):
    """执行回测"""
    df = data.copy()
    
    # 计算收益率
    df['daily_return'] = df['close'].pct_change()
    df['strategy_return'] = df['position'] * df['daily_return']
    
    # 净值曲线
    df['market_nav'] = (1 + df['daily_return']).cumprod() * initial_capital
    df['strategy_nav'] = (1 + df['strategy_return']).cumprod() * initial_capital
    
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
    
    # 卡尔玛比率
    calmar = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0
    
    # 胜率
    winning_days = (returns > 0).sum()
    total_days = (returns != 0).sum()
    win_rate = winning_days / total_days if total_days > 0 else 0
    
    # 盈亏比
    avg_gain = returns[returns > 0].mean() if (returns > 0).any() else 0
    avg_loss = abs(returns[returns < 0].mean()) if (returns < 0).any() else 1
    profit_loss_ratio = avg_gain / avg_loss if avg_loss > 0 else 0
    
    # 交易次数
    trades = df[df['trade'] == True]
    
    # 周期统计
    avg_short = df['ama_short_period'].mean()
    avg_long = df['ama_long_period'].mean()
    
    metrics = {
        '总收益率': f"{total_return*100:.2f}%",
        '年化收益率': f"{annual_return*100:.2f}%",
        '年化波动率': f"{volatility*100:.2f}%",
        '最大回撤': f"{max_drawdown*100:.2f}%",
        '夏普比率': f"{sharpe:.3f}",
        '卡尔玛比率': f"{calmar:.3f}",
        '胜率': f"{win_rate*100:.2f}%",
        '盈亏比': f"{profit_loss_ratio:.2f}",
        '交易次数': int(len(trades)),
        '持仓天数': int(df['position'].sum()),
        '平均短周期': f"{avg_short:.1f}",
        '平均长周期': f"{avg_long:.1f}",
        '基准总收益': f"{market_return*100:.2f}%",
        '基准年化': f"{market_annual*100:.2f}%",
        '基准最大回撤': f"{market_max_dd*100:.2f}%",
        '基准夏普': f"{market_sharpe:.3f}",
    }
    
    return metrics


# ============================================================
# 可视化
# ============================================================

def plot_results(df, save_path='double_sword_v3_final_backtest.png'):
    """绘制回测图表"""
    fig, axes = plt.subplots(5, 1, figsize=(16, 18))
    
    # 图1: 净值曲线
    ax1 = axes[0]
    ax1.plot(df.index, df['market_nav'], label='CSI300 Index', linewidth=1.5, color='gray', alpha=0.7)
    ax1.plot(df.index, df['strategy_nav'], label='Double Sword V3 Final', linewidth=2, color='#e74c3c')
    
    buy_signals = df[df['ds_signal'].diff() > 0]
    sell_signals = df[df['ds_signal'].diff() < 0]
    
    if len(buy_signals) > 0:
        ax1.scatter(buy_signals.index, buy_signals['strategy_nav'], 
                   marker='^', color='green', s=60, label='Buy', zorder=5)
    if len(sell_signals) > 0:
        ax1.scatter(sell_signals.index, sell_signals['strategy_nav'], 
                   marker='v', color='red', s=60, label='Sell', zorder=5)
    
    ax1.set_title('Double Sword V3 Final - Adaptive Period & Threshold', fontsize=16, fontweight='bold')
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
    
    # 图3: 仓位
    ax3 = axes[2]
    ax3.fill_between(df.index, 0, df['position'], alpha=0.5, color='green')
    ax3.set_ylabel('Position')
    ax3.set_title('Position Over Time')
    ax3.set_ylim(-0.1, 1.2)
    ax3.grid(True, alpha=0.3)
    
    # 图4: 周期演变
    ax4 = axes[3]
    ax4.plot(df.index, df['ama_short_period'], label='AMA Short Period', color='blue')
    ax4.plot(df.index, df['ama_long_period'], label='AMA Long Period', color='red')
    ax4.axhline(y=15, color='blue', linestyle='--', alpha=0.3, label='Base Short (15)')
    ax4.axhline(y=40, color='red', linestyle='--', alpha=0.3, label='Base Long (40)')
    ax4.set_ylabel('Period')
    ax4.set_title('Adaptive Periods (Based on ADX)')
    ax4.legend()
    ax4.grid(True, alpha=0.3)
    
    # 图5: 阈值演变
    ax5 = axes[4]
    ax5.plot(df.index, df['ama_ratio'], label='AMA Ratio', color='purple', alpha=0.7)
    ax5.plot(df.index, df['adaptive_threshold'], label='Adaptive Threshold', 
             color='red', linewidth=2)
    ax5.fill_between(df.index, df['adaptive_threshold'], alpha=0.2, color='red')
    ax5.set_ylabel('Ratio')
    ax5.set_xlabel('Date')
    ax5.set_title('Adaptive Threshold (70% Quantile)')
    ax5.legend()
    ax5.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    print(f"图表已保存: {save_path}")
    plt.close()


def generate_report(metrics, df, output_path='double_sword_v3_final_report.txt'):
    """生成策略报告"""
    
    trades_df = df[df['trade'] == True].copy()
    
    report = f"""
================================================================================
               双剑合璧V3 Final - 策略回测报告
        Adaptive Period + Adaptive Threshold Edition
================================================================================

一、策略概述
--------------------------------------------------------------------------------
策略来源: 华创证券涨跌停剪刀差择时系列

核心优化:
1. 周期自适应: 根据ADX趋势强度动态调整AMA周期
   - 强趋势(ADX>40): 周期延长至 ~21/56 (减少假信号)
   - 震荡(ADX<20): 周期缩短至 ~9/24 (快速响应)
   - 基础周期: 15/40

2. 阈值自适应: 使用AMA比率的70%滚动分位数
   - 牛市阈值自动上移, 熊市自动下移
   - 始终取前70%水平作为门槛

二、回测参数
--------------------------------------------------------------------------------
回测标的: 沪深300指数 (000300.SH)
回测区间: {df.index[0].strftime('%Y-%m-%d')} ~ {df.index[-1].strftime('%Y-%m-%d')}
数据周期: 日线
初始资金: 1.0

三、回测结果
--------------------------------------------------------------------------------
                          策略表现                基准(沪深300)
--------------------------------------------------------------------------------
总收益率:          {metrics['总收益率']:>15s}     {metrics['基准总收益']:>15s}
年化收益率:        {metrics['年化收益率']:>15s}     {metrics['基准年化']:>15s}
年化波动率:        {metrics['年化波动率']:>15s}     -
最大回撤:          {metrics['最大回撤']:>15s}     {metrics['基准最大回撤']:>15s}
夏普比率:          {metrics['夏普比率']:>15s}     {metrics['基准夏普']:>15s}
卡尔玛比率:        {metrics['卡尔玛比率']:>15s}     -
胜率:              {metrics['胜率']:>15s}     -
盈亏比:            {metrics['盈亏比']:>15s}     -
交易次数:          {str(metrics['交易次数']):>15s}     -
持仓天数:          {str(metrics['持仓天数']):>15s}     -
平均短周期:        {metrics['平均短周期']:>15s}     -
平均长周期:        {metrics['平均长周期']:>15s}     -
--------------------------------------------------------------------------------

四、信号统计
--------------------------------------------------------------------------------
推波助澜做多天数:   {int(df['tb_signal'].sum())} 天
价量共振做多天数:   {int(df['pv_signal'].sum())} 天
双剑合璧做多天数:   {int(df['ds_signal'].sum())} 天
平均仓位:           {df['position'].mean()*100:.1f}%

五、策略评价
--------------------------------------------------------------------------------
"""
    
    sharpe = float(metrics['夏普比率'])
    max_dd = float(metrics['最大回撤'].rstrip('%'))
    calmar = float(metrics['卡尔玛比率'])
    
    if sharpe > 1.0:
        report += "✓ 夏普比率 > 1.0，风险调整后收益优秀\n"
    elif sharpe > 0.8:
        report += "✓ 夏普比率 > 0.8，风险调整后收益良好\n"
    
    if calmar > 1.0:
        report += "✓ 卡尔玛比率 > 1.0，收益/回撤比优秀\n"
    
    if abs(max_dd) < 15:
        report += "✓ 最大回撤控制在15%以内，风控优秀\n"
    
    strategy_return = float(metrics['总收益率'].rstrip('%'))
    benchmark_return = float(metrics['基准总收益'].rstrip('%'))
    if strategy_return > benchmark_return:
        report += f"✓ 策略跑赢基准 {strategy_return - benchmark_return:.2f}%\n"
    else:
        report += f"○ 策略跑输基准 {benchmark_return - strategy_return:.2f}% (牛市中择时策略正常现象)\n"
    
    report += f"""
六、风险提示
--------------------------------------------------------------------------------
1. 本策略基于历史数据回测，不代表未来表现
2. 自适应参数可能导致过拟合，建议持续监控
3. 极端行情下策略可能失效
4. 建议结合其他指标综合判断

================================================================================
报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
================================================================================
"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(report)
    return output_path


# ============================================================
# 主函数
# ============================================================

def main():
    """主函数"""
    print("="*80)
    print("双剑合璧V3 Final - 周期自适应 + 阈值自适应")
    print("="*80)
    
    # 1. 加载数据
    print("\n[1/5] 加载数据...")
    df = load_data()
    print(f"  加载 {len(df)} 条数据")
    print(f"  时间范围: {df.index[0].date()} ~ {df.index[-1].date()}")
    
    # 2. 计算策略信号
    print("\n[2/5] 计算双剑合璧V3 Final信号...")
    data = double_sword_v3_final(df)
    print(f"  推波助澜做多: {int(data['tb_signal'].sum())} 天")
    print(f"  价量共振做多: {int(data['pv_signal'].sum())} 天")
    print(f"  双剑合璧做多: {int(data['ds_signal'].sum())} 天")
    print(f"  平均周期: {data['ama_short_period'].mean():.1f}/{data['ama_long_period'].mean():.1f}")
    
    # 3. 回测
    print("\n[3/5] 执行回测...")
    result = backtest(data)
    
    # 4. 计算指标
    print("\n[4/5] 计算绩效指标...")
    metrics = calculate_metrics(result)
    
    print(f"\n  策略总收益: {metrics['总收益率']}")
    print(f"  基准总收益: {metrics['基准总收益']}")
    print(f"  夏普比率: {metrics['夏普比率']}")
    print(f"  最大回撤: {metrics['最大回撤']}")
    
    # 5. 生成报告和图表
    print("\n[5/5] 生成报告和图表...")
    report_path = generate_report(metrics, result)
    chart_path = plot_results(result)
    
    print("\n" + "="*80)
    print("回测完成!")
    print(f"报告文件: {report_path}")
    print(f"图表文件: {chart_path}")
    print("="*80)
    
    return result, metrics


if __name__ == "__main__":
    result, metrics = main()
