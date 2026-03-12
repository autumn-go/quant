#!/usr/bin/env python3
"""
双剑合璧V3 Final - 完全重写版
直接从成分股数据计算所有指标，不依赖涨跌停表

推波助澜V3指标（直接从个股数据计算）：
1. 涨跌停比率剪刀差 = (涨停数 - 跌停数) / 总数
   涨停: pct_change > 9.5%
   跌停: pct_change < -9.5%
   
2. 连板比率剪刀差 = (连板涨停数 - 连板跌停数) / 总数
   连板涨停: 今日和昨日涨幅都 > 9.5%
   连板跌停: 今日和昨日跌幅都 < -9.5%
   
3. 地天板/天地板比率剪刀差
   地天板: (low - 昨收)/昨收 < -7% 且 (close - 昨收)/昨收 > 7%
   天地板: (high - 昨收)/昨收 > 7% 且 (close - 昨收)/昨收 < -7%

价量共振V3指标：
- BMA50, AMA5/AMA100, 价能, 量能, 效率指标, 动量指标

信号分层：
- 两者共振 → 满仓(1.0)
- 单一触发 → 半仓(0.5)
- 无信号 → 空仓(0)
"""

import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

DB_PATH = '/root/.openclaw/workspace/quant-main/data-collector/csi300_data.db'
plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'SimHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False


def load_data():
    """加载数据"""
    conn = sqlite3.connect(DB_PATH)
    
    # 指数数据
    df_index = pd.read_sql_query('''
        SELECT date, open, high, low, close, volume, amount
        FROM csi300_index_daily 
        WHERE date >= '20190101'
        ORDER BY date
    ''', conn)
    df_index['date'] = pd.to_datetime(df_index['date'])
    df_index.set_index('date', inplace=True)
    df_index.sort_index(inplace=True)
    
    # 成分股数据（用于计算所有指标）
    df_stocks = pd.read_sql_query('''
        SELECT symbol, date, open, high, low, close, volume, amount, pct_change
        FROM csi300_stock_daily 
        WHERE date >= '20190101'
        ORDER BY symbol, date
    ''', conn)
    df_stocks['date'] = pd.to_datetime(df_stocks['date'])
    
    conn.close()
    return df_index, df_stocks


def calculate_tuibo_from_stocks(df_stocks):
    """
    从成分股数据计算推波助澜V3的所有指标
    """
    df = df_stocks.copy()
    df = df.sort_values(['symbol', 'date'])
    
    # 计算昨日收盘（用于地天板/天地板计算）
    df['prev_close'] = df.groupby('symbol')['close'].shift(1)
    df['prev_pct'] = df.groupby('symbol')['pct_change'].shift(1)
    
    # ========== 1. 涨跌停判断 ==========
    # 涨停: 涨幅 > 9.5%
    df['is_up_limit'] = df['pct_change'] > 9.5
    # 跌停: 跌幅 < -9.5%
    df['is_down_limit'] = df['pct_change'] < -9.5
    
    # ========== 2. 连板判断 ==========
    # 连板涨停: 今日和昨日涨幅都 > 9.5%
    df['is_consecutive_up'] = (df['pct_change'] > 9.5) & (df['prev_pct'] > 9.5)
    # 连板跌停: 今日和昨日跌幅都 < -9.5%
    df['is_consecutive_down'] = (df['pct_change'] < -9.5) & (df['prev_pct'] < -9.5)
    
    # ========== 3. 地天板/天地板判断 ==========
    # 计算相对昨收的高低涨幅
    df['high_from_prev'] = (df['high'] - df['prev_close']) / df['prev_close'] * 100
    df['low_from_prev'] = (df['low'] - df['prev_close']) / df['prev_close'] * 100
    df['close_from_prev'] = df['pct_change']  # 就是当日涨跌幅
    
    # 地天板: 盘中最低相对昨收 < -7%，收盘相对昨收 > 7%
    df['is_dtb'] = (df['low_from_prev'] < -7) & (df['close_from_prev'] > 7)
    # 天地板: 盘中最高相对昨收 > 7%，收盘相对昨收 < -7%
    df['is_tdb'] = (df['high_from_prev'] > 7) & (df['close_from_prev'] < -7)
    
    # ========== 按日汇总 ==========
    daily_stats = []
    
    for date, group in df.groupby('date'):
        total = len(group)
        if total == 0:
            continue
        
        # 1. 涨跌停比率剪刀差（成交额加权）
        up_stocks = group[group['is_up_limit']]
        down_stocks = group[group['is_down_limit']]
        
        total_amount = group['amount'].sum()
        if total_amount > 0:
            up_amount = up_stocks['amount'].sum()
            down_amount = down_stocks['amount'].sum()
            limit_scissors = (up_amount - down_amount) / total_amount
        else:
            limit_scissors = 0
        
        # 2. 连板比率剪刀差
        consecutive_up = group['is_consecutive_up'].sum()
        consecutive_down = group['is_consecutive_down'].sum()
        consecutive_scissors = (consecutive_up - consecutive_down) / total
        
        # 3. 地天板/天地板比率剪刀差
        dtb_count = group['is_dtb'].sum()
        tdb_count = group['is_tdb'].sum()
        dtb_tdb_scissors = (dtb_count - tdb_count) / total
        
        daily_stats.append({
            'date': date,
            'limit_scissors': limit_scissors,
            'consecutive_scissors': consecutive_scissors,
            'dtb_tdb_scissors': dtb_tdb_scissors,
            'up_count': up_stocks.shape[0],
            'down_count': down_stocks.shape[0],
            'consecutive_up_count': consecutive_up,
            'consecutive_down_count': consecutive_down,
            'dtb_count': dtb_count,
            'tdb_count': tdb_count
        })
    
    return pd.DataFrame(daily_stats)


def calculate_tuibo_v3(df_index, df_stocks):
    """计算推波助澜V3"""
    data = df_index.copy()
    
    print("从成分股数据计算推波助澜V3指标...")
    tuibo_df = calculate_tuibo_from_stocks(df_stocks)
    tuibo_df.set_index('date', inplace=True)
    
    # 合并到指数数据
    data = data.join(tuibo_df, how='left')
    
    # 填充缺失值
    data['limit_scissors'] = data['limit_scissors'].fillna(0)
    data['consecutive_scissors'] = data['consecutive_scissors'].fillna(0)
    data['dtb_tdb_scissors'] = data['dtb_tdb_scissors'].fillna(0)
    
    # 推波助澜比率 = 三个指标等权平均
    data['tuibo_ratio'] = (data['limit_scissors'] + 
                           data['consecutive_scissors'] + 
                           data['dtb_tdb_scissors']) / 3
    
    # AMA30和AMA100
    data['ama30'] = data['tuibo_ratio'].rolling(window=30).mean()
    data['ama100'] = data['tuibo_ratio'].rolling(window=100).mean()
    
    # 做多信号
    data['ama_ratio'] = data['ama30'] / data['ama100'].replace(0, np.nan)
    data['tb_signal'] = np.where(
        (data['ama_ratio'] > 1.15) & 
        (data['ama30'] > 0) & 
        (data['ama100'] > 0), 1, 0
    )
    
    return data


def calculate_price_volume_resonance_v3(df):
    """价量共振V3"""
    data = df.copy()
    
    # BMA50
    data['bma50'] = data['close'].rolling(window=50).mean()
    
    # AMA5/AMA100 (成交量)
    data['ama5_vol'] = data['volume'].ewm(span=5, adjust=False).mean()
    data['ama100_vol'] = data['volume'].ewm(span=100, adjust=False).mean()
    
    # 价能 = BMA(Today) / BMA(Today-3)
    data['price_energy'] = data['bma50'] / data['bma50'].shift(3)
    
    # 量能 = AMA5 / AMA100
    data['volume_energy'] = data['ama5_vol'] / data['ama100_vol']
    
    # 价量共振指标
    data['pv_indicator'] = data['price_energy'] * data['volume_energy']
    
    # 多空市场判断
    data['ma5'] = data['close'].rolling(window=5).mean()
    data['ma90'] = data['close'].rolling(window=90).mean()
    data['is_bull'] = data['ma5'] > data['ma90']
    
    # 阈值
    data['threshold'] = np.where(data['is_bull'], 1.125, 1.275)
    
    # 基础持仓
    data['position_raw'] = np.where(data['pv_indicator'] > data['threshold'], 1, 0)
    
    # 趋势强劲下跌过滤
    weights = [0.4, 0.3, 0.2, 0.1]
    data['smooth_close'] = data['close'].rolling(window=4).apply(
        lambda x: np.sum(x * weights), raw=True
    )
    
    price_diff = data['smooth_close'].diff().abs()
    total_movement = price_diff.rolling(window=10).sum()
    net_movement = (data['smooth_close'] - data['smooth_close'].shift(10)).abs()
    data['efficiency'] = (net_movement / total_movement.replace(0, np.nan)) * 100
    data['momentum'] = (data['smooth_close'] - data['smooth_close'].shift(10)) / data['smooth_close'].shift(10)
    
    data['strong_downtrend'] = (data['efficiency'] > 50) & (data['momentum'] < 0)
    data['pv_signal'] = np.where(data['strong_downtrend'], 0, data['position_raw'])
    
    return data


def double_sword_v3_tiered(df_index, df_stocks):
    """双剑合璧V3：信号分层"""
    print("计算推波助澜V3...")
    data = calculate_tuibo_v3(df_index.copy(), df_stocks)
    
    print("计算价量共振V3...")
    data_pv = calculate_price_volume_resonance_v3(df_index.copy())
    data['pv_signal'] = data_pv['pv_signal']
    
    # 信号分层
    data['strong_signal'] = ((data['tb_signal'] == 1) & (data['pv_signal'] == 1)).astype(int)
    data['weak_signal'] = (((data['tb_signal'] == 1) | (data['pv_signal'] == 1)) & 
                           (data['strong_signal'] == 0)).astype(int)
    
    # 仓位：共振=满仓，单一=半仓，无=空仓
    data['position_size'] = data['strong_signal'] * 1.0 + data['weak_signal'] * 0.5
    
    # 延迟1天执行
    data['position'] = data['position_size'].shift(1).fillna(0)
    
    return data


def backtest(data):
    """回测"""
    df = data.copy()
    df['daily_return'] = df['close'].pct_change()
    df['strategy_return'] = df['position'] * df['daily_return']
    
    df['market_nav'] = (1 + df['daily_return']).cumprod()
    df['strategy_nav'] = (1 + df['strategy_return']).cumprod()
    
    df['trade'] = df['position'].diff().abs() > 0.01
    return df


def calculate_metrics(df):
    """计算指标"""
    returns = df['strategy_return'].dropna()
    total_return = df['strategy_nav'].iloc[-1] - 1
    n_days = len(returns)
    annual_return = (1 + total_return) ** (252 / n_days) - 1 if total_return > -1 else -1
    volatility = returns.std() * np.sqrt(252) if returns.std() > 0 else 0
    sharpe = annual_return / volatility if volatility > 0 else 0
    
    cummax = df['strategy_nav'].cummax()
    max_drawdown = ((df['strategy_nav'] - cummax) / cummax).min()
    
    market_return = df['market_nav'].iloc[-1] - 1
    
    return {
        '总收益': f"{total_return*100:.2f}%",
        '年化': f"{annual_return*100:.2f}%",
        '夏普': f"{sharpe:.3f}",
        '回撤': f"{max_drawdown*100:.2f}%",
        '交易': int(df['trade'].sum()),
        '持仓': f"{df['position'].mean()*100:.1f}%",
        '强信号': int(df['strong_signal'].sum()),
        '弱信号': int(df['weak_signal'].sum()),
        '基准': f"{market_return*100:.2f}%"
    }


def plot_results(df, save_path='double_sword_v3_final_backtest.png'):
    """绘制图表"""
    fig, axes = plt.subplots(4, 1, figsize=(16, 12))
    
    # 图1: 净值曲线
    ax1 = axes[0]
    ax1.plot(df.index, df['market_nav'], label='CSI300 Index', linewidth=1.5, color='gray', alpha=0.6)
    ax1.plot(df.index, df['strategy_nav'], label='Double Sword V3', linewidth=2, color='#e74c3c')
    
    # 标记信号点
    strong_buy = df[df['strong_signal'].diff() > 0]
    weak_buy = df[df['weak_signal'].diff() > 0]
    sell = df[df['position'].diff() < -0.1]
    
    if len(strong_buy) > 0:
        ax1.scatter(strong_buy.index, strong_buy['strategy_nav'], marker='^', color='darkgreen', s=80, 
                   label='Strong Buy (Full)', zorder=10)
    if len(weak_buy) > 0:
        ax1.scatter(weak_buy.index, weak_buy['strategy_nav'], marker='^', color='orange', s=50, 
                   label='Weak Buy (Half)', zorder=10)
    if len(sell) > 0:
        ax1.scatter(sell.index, sell['strategy_nav'], marker='v', color='red', s=60, 
                   label='Sell/Clear', zorder=10)
    
    ax1.set_title('Double Sword V3 Final - 2019-2026 (Rewritten)', fontsize=14, fontweight='bold')
    ax1.set_ylabel('Net Value')
    ax1.legend(loc='upper left', fontsize=9)
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
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # 图3: 仓位
    ax3 = axes[2]
    ax3.fill_between(df.index, 0, df['position'], alpha=0.3, color='blue', label='Position')
    ax3.fill_between(df.index, 0, df['strong_signal'], alpha=0.6, color='green', label='Full (1.0)')
    ax3.fill_between(df.index, 0, df['weak_signal'] * 0.5, alpha=0.6, color='orange', label='Half (0.5)')
    ax3.axhline(y=1.0, color='green', linestyle='--', alpha=0.5)
    ax3.axhline(y=0.5, color='orange', linestyle='--', alpha=0.5)
    ax3.set_ylabel('Position')
    ax3.set_ylim(-0.1, 1.2)
    ax3.legend(loc='upper right', fontsize=9)
    ax3.grid(True, alpha=0.3)
    
    # 图4: 子策略信号
    ax4 = axes[3]
    ax4.fill_between(df.index, 0, df['tb_signal'], alpha=0.4, color='blue', label='Tuibo Zhulan')
    ax4.fill_between(df.index, 0, df['pv_signal'], alpha=0.4, color='orange', label='Price-Volume')
    ax4.fill_between(df.index, 0, df['strong_signal'], alpha=0.7, color='green', label='Both')
    ax4.set_ylabel('Signals')
    ax4.set_xlabel('Date')
    ax4.set_ylim(-0.1, 1.2)
    ax4.legend(loc='upper right', fontsize=9)
    ax4.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    print(f"\n图表已保存: {save_path}")
    plt.close()


def main():
    print("="*70)
    print("双剑合璧V3 Final - 完全重写版")
    print("直接从成分股数据计算所有指标（不依赖涨跌停表）")
    print("="*70)
    
    df_index, df_stocks = load_data()
    print(f"\n数据加载:")
    print(f"  指数: {len(df_index)} 天 ({df_index.index[0].date()} ~ {df_index.index[-1].date()})")
    print(f"  成分股: {len(df_stocks)} 条记录")
    print(f"  成分股数量: {df_stocks['symbol'].nunique()} 只")
    
    # 运行策略
    data = double_sword_v3_tiered(df_index, df_stocks)
    
    # 回测
    result = backtest(data)
    metrics = calculate_metrics(result)
    
    print(f"\n" + "="*70)
    print("回测结果 (2019-2026)")
    print("="*70)
    print(f"策略总收益: {metrics['总收益']}")
    print(f"策略年化:   {metrics['年化']}")
    print(f"策略夏普:   {metrics['夏普']}")
    print(f"策略回撤:   {metrics['回撤']}")
    print(f"交易次数:   {metrics['交易']}")
    print(f"平均仓位:   {metrics['持仓']}")
    print(f"\n基准总收益: {metrics['基准']}")
    
    print(f"\n信号统计:")
    print(f"  强信号(共振): {metrics['强信号']} 天 → 满仓(1.0)")
    print(f"  弱信号(单一): {metrics['弱信号']} 天 → 半仓(0.5)")
    
    # 生成图表
    plot_results(result)
    
    print("\n" + "="*70)
    print("重写版改进:")
    print("  ✅ 直接从成分股计算涨跌停（不依赖涨跌停表）")
    print("  ✅ 2019-2022年数据完整可用")
    print("  ✅ 天地板/地天板从high/low计算")
    print("  ✅ 连板从连续两日涨跌幅计算")
    print("="*70)


if __name__ == "__main__":
    main()
