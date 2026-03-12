#!/usr/bin/env python3
"""
双剑合璧V3 - 信号分层版

持仓规则：
- 两个策略都做多（共振）→ 满仓（1.0）
- 只有一个做多 → 半仓（0.5）
- 都不做多 → 空仓（0）
"""

import sqlite3
import pandas as pd
import numpy as np
import re

DB_PATH = '/root/.openclaw/workspace/quant-main/data-collector/csi300_data.db'


def load_data():
    """加载数据"""
    conn = sqlite3.connect(DB_PATH)
    
    df_index = pd.read_sql_query('''
        SELECT date, open, high, low, close, volume, amount
        FROM csi300_index_daily ORDER BY date
    ''', conn)
    df_index['date'] = pd.to_datetime(df_index['date'])
    df_index.set_index('date', inplace=True)
    df_index.sort_index(inplace=True)
    
    df_stocks = pd.read_sql_query('''
        SELECT symbol, date, open, high, low, close, volume, amount, pct_change
        FROM csi300_stock_daily WHERE date >= '20230101'
    ''', conn)
    df_stocks['date'] = pd.to_datetime(df_stocks['date'])
    
    df_limit = pd.read_sql_query('''
        SELECT date, code, name, close, pct_change, limit_type, status
        FROM limit_up_down WHERE date >= '20230101'
    ''', conn)
    df_limit['date'] = pd.to_datetime(df_limit['date'])
    
    conn.close()
    
    return df_index, df_stocks, df_limit


# ============================================================
# 价量共振V3
# ============================================================

def calculate_price_volume_resonance_v3(df):
    """价量共振V3"""
    data = df.copy()
    
    data['bma50'] = data['close'].rolling(window=50).mean()
    data['ama5_vol'] = data['volume'].ewm(span=5, adjust=False).mean()
    data['ama100_vol'] = data['volume'].ewm(span=100, adjust=False).mean()
    
    data['price_energy'] = data['bma50'] / data['bma50'].shift(3)
    data['volume_energy'] = data['ama5_vol'] / data['ama100_vol']
    data['pv_indicator'] = data['price_energy'] * data['volume_energy']
    
    data['ma5'] = data['close'].rolling(window=5).mean()
    data['ma90'] = data['close'].rolling(window=90).mean()
    data['is_bull'] = data['ma5'] > data['ma90']
    
    data['threshold'] = np.where(data['is_bull'], 1.125, 1.275)
    data['position_raw'] = np.where(data['pv_indicator'] > data['threshold'], 1, 0)
    
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


# ============================================================
# 推波助澜V3
# ============================================================

def calculate_limit_scissors(df_limit, df_stocks):
    """涨跌停比率剪刀差（成交额加权）"""
    daily_stats = []
    
    for date, group in df_limit.groupby('date'):
        up_stocks = group[group['limit_type'] == 'up']
        down_stocks = group[group['limit_type'] == 'down']
        
        day_stocks = df_stocks[df_stocks['date'] == date]
        total_amount = day_stocks['amount'].sum()
        
        if total_amount == 0:
            limit_scissors = 0
        else:
            up_amount = 0
            for _, row in up_stocks.iterrows():
                code = row['code']
                stock_data = day_stocks[day_stocks['symbol'].str.contains(code)]
                if not stock_data.empty:
                    up_amount += stock_data['amount'].iloc[0]
            
            down_amount = 0
            for _, row in down_stocks.iterrows():
                code = row['code']
                stock_data = day_stocks[day_stocks['symbol'].str.contains(code)]
                if not stock_data.empty:
                    down_amount += stock_data['amount'].iloc[0]
            
            limit_scissors = (up_amount - down_amount) / total_amount
        
        daily_stats.append({'date': date, 'limit_scissors': limit_scissors})
    
    return pd.DataFrame(daily_stats)


def calculate_consecutive_scissors(df_stocks):
    """连板比率剪刀差"""
    df_stocks = df_stocks.copy()
    df_stocks = df_stocks.sort_values(['symbol', 'date'])
    df_stocks['prev_pct'] = df_stocks.groupby('symbol')['pct_change'].shift(1)
    
    df_stocks['consecutive_up'] = (df_stocks['pct_change'] > 9.5) & (df_stocks['prev_pct'] > 9.5)
    df_stocks['consecutive_down'] = (df_stocks['pct_change'] < -9.5) & (df_stocks['prev_pct'] < -9.5)
    
    daily_stats = []
    for date, group in df_stocks.groupby('date'):
        total = len(group)
        if total == 0:
            continue
        
        up_ratio = group['consecutive_up'].sum() / total
        down_ratio = group['consecutive_down'].sum() / total
        
        daily_stats.append({'date': date, 'consecutive_scissors': up_ratio - down_ratio})
    
    return pd.DataFrame(daily_stats)


def calculate_dtb_tdb_scissors(df_stocks):
    """地天板/天地板比率剪刀差"""
    df_stocks = df_stocks.copy()
    df_stocks = df_stocks.sort_values(['symbol', 'date'])
    df_stocks['prev_close'] = df_stocks.groupby('symbol')['close'].shift(1)
    
    df_stocks['high_pct'] = (df_stocks['high'] - df_stocks['prev_close']) / df_stocks['prev_close'] * 100
    df_stocks['low_pct'] = (df_stocks['low'] - df_stocks['prev_close']) / df_stocks['prev_close'] * 100
    
    df_stocks['dtb'] = (df_stocks['low_pct'] < -7) & (df_stocks['pct_change'] > 7)
    df_stocks['tdb'] = (df_stocks['high_pct'] > 7) & (df_stocks['pct_change'] < -7)
    
    daily_stats = []
    for date, group in df_stocks.groupby('date'):
        total = len(group)
        if total == 0:
            continue
        
        dtb_ratio = group['dtb'].sum() / total
        tdb_ratio = group['tdb'].sum() / total
        
        daily_stats.append({'date': date, 'dtb_tdb_scissors': dtb_ratio - tdb_ratio})
    
    return pd.DataFrame(daily_stats)


def calculate_tuibo_v3(df_index, df_stocks, df_limit):
    """推波助澜V3"""
    data = df_index.copy()
    
    limit_df = calculate_limit_scissors(df_limit, df_stocks)
    limit_df.set_index('date', inplace=True)
    
    cons_df = calculate_consecutive_scissors(df_stocks)
    cons_df.set_index('date', inplace=True)
    
    dtb_df = calculate_dtb_tdb_scissors(df_stocks)
    dtb_df.set_index('date', inplace=True)
    
    data = data.join(limit_df[['limit_scissors']], how='left')
    data = data.join(cons_df[['consecutive_scissors']], how='left')
    data = data.join(dtb_df[['dtb_tdb_scissors']], how='left')
    
    data['limit_scissors'] = data['limit_scissors'].fillna(0)
    data['consecutive_scissors'] = data['consecutive_scissors'].fillna(0)
    data['dtb_tdb_scissors'] = data['dtb_tdb_scissors'].fillna(0)
    
    data['tuibo_ratio'] = (data['limit_scissors'] + data['consecutive_scissors'] + data['dtb_tdb_scissors']) / 3
    
    data['ama30'] = data['tuibo_ratio'].rolling(window=30).mean()
    data['ama100'] = data['tuibo_ratio'].rolling(window=100).mean()
    
    data['ama_ratio'] = data['ama30'] / data['ama100']
    data['tb_signal'] = np.where(
        (data['ama_ratio'] > 1.15) & (data['ama30'] > 0) & (data['ama100'] > 0), 1, 0
    )
    
    return data


# ============================================================
# 双剑合璧V3 - 信号分层
# ============================================================

def double_sword_v3_tiered(df_index, df_stocks, df_limit):
    """双剑合璧V3：信号分层"""
    print("计算价量共振V3...")
    data_pv = calculate_price_volume_resonance_v3(df_index.copy())
    
    print("计算推波助澜V3...")
    data_tb = calculate_tuibo_v3(df_index.copy(), df_stocks, df_limit)
    
    data = df_index.copy()
    data['pv_signal'] = data_pv['pv_signal']
    data['tb_signal'] = data_tb['tb_signal']
    
    # 信号分层
    # 强信号（两者共振）→ 满仓
    # 弱信号（单一）→ 半仓
    # 空仓 → 0
    data['strong_signal'] = ((data['tb_signal'] == 1) & (data['pv_signal'] == 1)).astype(int)
    data['weak_signal'] = (((data['tb_signal'] == 1) | (data['pv_signal'] == 1)) & 
                           (data['strong_signal'] == 0)).astype(int)
    
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
    
    df['trade'] = df['position'].diff().abs() > 0.01  # 仓位变化>1%视为调仓
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


def main():
    print("="*60)
    print("双剑合璧V3 - 信号分层版")
    print("共振=满仓，单一=半仓，无=空仓")
    print("="*60)
    
    df_index, df_stocks, df_limit = load_data()
    print(f"\n数据：指数{len(df_index)}天，个股{len(df_stocks)}条，涨跌停{len(df_limit)}条")
    
    data = double_sword_v3_tiered(df_index, df_stocks, df_limit)
    
    result = backtest(data)
    metrics = calculate_metrics(result)
    
    print(f"\n信号统计：")
    print(f"  强信号（共振）：{metrics['强信号']} 天 → 满仓")
    print(f"  弱信号（单一）：{metrics['弱信号']} 天 → 半仓")
    print(f"  平均仓位：{metrics['持仓']}")
    
    print(f"\n" + "="*60)
    print("回测结果 (2023-2026)")
    print("="*60)
    print(f"策略总收益：{metrics['总收益']}")
    print(f"策略年化：{metrics['年化']}")
    print(f"策略夏普：{metrics['夏普']}")
    print(f"策略回撤：{metrics['回撤']}")
    print(f"交易次数：{metrics['交易']}")
    print(f"\n基准总收益：{metrics['基准']}")
    
    print(f"\n" + "="*60)
    print("对比总结")
    print("="*60)
    print("信号分层 vs 或逻辑：")
    print("  - 强信号时满仓，弱信号时半仓")
    print("  - 降低单一策略误判带来的风险")
    print("  - 可能在震荡市表现更稳健")


if __name__ == "__main__":
    main()
