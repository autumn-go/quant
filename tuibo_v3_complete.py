#!/usr/bin/env python3
"""
推波助澜V3 - 完整实现

三个维度市场情绪剪刀差：
1. 涨跌停比率剪刀差（成交额加权）
   (涨停成交额 - 跌停成交额) / 总成交额
   
2. 连板比率剪刀差
   连续涨停比率 - 连续跌停比率
   连续涨停：今日和昨日涨幅均 > 9.5%
   连续跌停：今日和昨日跌幅均 < -9.5%
   
3. 地天板/天地板比率剪刀差
   地天板：今日最低相对昨收 < -7%，收盘相对昨收 > 7%
   天地板：今日最高相对昨收 > 7%，收盘相对昨收 < -7%
   
推波助澜比率 = 三个指标等权相加
AMA30 = 30日简单均线
AMA100 = 100日简单均线

做多条件：
1. AMA30 / AMA100 > 1.15
2. AMA30 > 0
3. AMA100 > 0
"""

import sqlite3
import pandas as pd
import numpy as np
import re

DB_PATH = '/root/.openclaw/workspace/quant-main/data-collector/csi300_data.db'


def load_data():
    """加载数据"""
    conn = sqlite3.connect(DB_PATH)
    
    # 指数数据
    df_index = pd.read_sql_query('''
        SELECT date, open, high, low, close, volume, amount
        FROM csi300_index_daily ORDER BY date
    ''', conn)
    df_index['date'] = pd.to_datetime(df_index['date'])
    df_index.set_index('date', inplace=True)
    df_index.sort_index(inplace=True)
    
    # 成分股日K数据
    df_stocks = pd.read_sql_query('''
        SELECT symbol, date, open, high, low, close, volume, amount, pct_change
        FROM csi300_stock_daily WHERE date >= '20230101'
    ''', conn)
    df_stocks['date'] = pd.to_datetime(df_stocks['date'])
    
    # 涨跌停数据
    df_limit = pd.read_sql_query('''
        SELECT date, code, name, close, pct_change, limit_type, status
        FROM limit_up_down WHERE date >= '20230101'
    ''', conn)
    df_limit['date'] = pd.to_datetime(df_limit['date'])
    
    conn.close()
    
    return df_index, df_stocks, df_limit


def parse_consecutive_days(status):
    """
    解析连板天数
    返回: 连板天数 (1=首板, >=2=连板, 0=非涨停)
    """
    if pd.isna(status) or status == '':
        return 0
    
    status = str(status)
    
    # 首板
    if status == '首板':
        return 1
    
    # X连板
    match = re.search(r'(\d+)连板', status)
    if match:
        return int(match.group(1))
    
    # X天Y板，取Y
    match = re.search(r'\d+天(\d+)板', status)
    if match:
        return int(match.group(1))
    
    return 0


def calculate_limit_scissors(df_limit, df_stocks):
    """
    计算涨跌停比率剪刀差（成交额加权）
    """
    daily_stats = []
    
    for date, group in df_limit.groupby('date'):
        # 涨停数据
        up_stocks = group[group['limit_type'] == 'up']
        # 跌停数据
        down_stocks = group[group['limit_type'] == 'down']
        
        # 获取当日所有股票的成交额（用于加权）
        day_stocks = df_stocks[df_stocks['date'] == date]
        total_amount = day_stocks['amount'].sum()
        
        if total_amount == 0:
            limit_scissors = 0
        else:
            # 涨停成交额
            up_amount = 0
            for _, row in up_stocks.iterrows():
                code = row['code']
                stock_data = day_stocks[day_stocks['symbol'].str.contains(code)]
                if not stock_data.empty:
                    up_amount += stock_data['amount'].iloc[0]
            
            # 跌停成交额
            down_amount = 0
            for _, row in down_stocks.iterrows():
                code = row['code']
                stock_data = day_stocks[day_stocks['symbol'].str.contains(code)]
                if not stock_data.empty:
                    down_amount += stock_data['amount'].iloc[0]
            
            # 涨跌停比率剪刀差
            limit_scissors = (up_amount - down_amount) / total_amount
        
        daily_stats.append({
            'date': date,
            'limit_scissors': limit_scissors,
            'up_count': len(up_stocks),
            'down_count': len(down_stocks)
        })
    
    return pd.DataFrame(daily_stats)


def calculate_consecutive_scissors(df_stocks):
    """
    计算连板比率剪刀差
    连续涨停：今日和昨日涨幅均 > 9.5%
    连续跌停：今日和昨日跌幅均 < -9.5%
    """
    df_stocks = df_stocks.copy()
    df_stocks = df_stocks.sort_values(['symbol', 'date'])
    
    # 标记连续涨停/跌停
    df_stocks['prev_pct'] = df_stocks.groupby('symbol')['pct_change'].shift(1)
    
    # 连续涨停：今日和昨日涨幅均 > 9.5%
    df_stocks['consecutive_up'] = (df_stocks['pct_change'] > 9.5) & (df_stocks['prev_pct'] > 9.5)
    
    # 连续跌停：今日和昨日跌幅均 < -9.5%
    df_stocks['consecutive_down'] = (df_stocks['pct_change'] < -9.5) & (df_stocks['prev_pct'] < -9.5)
    
    # 按日统计
    daily_stats = []
    for date, group in df_stocks.groupby('date'):
        total = len(group)
        if total == 0:
            continue
        
        up_ratio = group['consecutive_up'].sum() / total
        down_ratio = group['consecutive_down'].sum() / total
        
        daily_stats.append({
            'date': date,
            'consecutive_scissors': up_ratio - down_ratio,
            'consecutive_up_count': group['consecutive_up'].sum(),
            'consecutive_down_count': group['consecutive_down'].sum()
        })
    
    return pd.DataFrame(daily_stats)


def calculate_dtb_tdb_scissors(df_stocks):
    """
    计算地天板/天地板比率剪刀差
    地天板：今日最低相对昨收 < -7%，收盘相对昨收 > 7%
    天地板：今日最高相对昨收 > 7%，收盘相对昨收 < -7%
    """
    df_stocks = df_stocks.copy()
    df_stocks = df_stocks.sort_values(['symbol', 'date'])
    
    # 获取昨日收盘
    df_stocks['prev_close'] = df_stocks.groupby('symbol')['close'].shift(1)
    
    # 计算相对昨收的涨跌幅
    df_stocks['high_pct'] = (df_stocks['high'] - df_stocks['prev_close']) / df_stocks['prev_close'] * 100
    df_stocks['low_pct'] = (df_stocks['low'] - df_stocks['prev_close']) / df_stocks['prev_close'] * 100
    df_stocks['close_pct'] = df_stocks['pct_change']  # 已包含在数据中
    
    # 地天板：最低 < -7%，收盘 > 7%
    df_stocks['dtb'] = (df_stocks['low_pct'] < -7) & (df_stocks['close_pct'] > 7)
    
    # 天地板：最高 > 7%，收盘 < -7%
    df_stocks['tdb'] = (df_stocks['high_pct'] > 7) & (df_stocks['close_pct'] < -7)
    
    # 按日统计
    daily_stats = []
    for date, group in df_stocks.groupby('date'):
        total = len(group)
        if total == 0:
            continue
        
        dtb_ratio = group['dtb'].sum() / total
        tdb_ratio = group['tdb'].sum() / total
        
        daily_stats.append({
            'date': date,
            'dtb_tdb_scissors': dtb_ratio - tdb_ratio,
            'dtb_count': group['dtb'].sum(),
            'tdb_count': group['tdb'].sum()
        })
    
    return pd.DataFrame(daily_stats)


def calculate_tuibo_v3(df_index, df_stocks, df_limit):
    """
    计算推波助澜V3
    """
    data = df_index.copy()
    
    # 计算三个剪刀差
    print("计算涨跌停比率剪刀差...")
    limit_df = calculate_limit_scissors(df_limit, df_stocks)
    limit_df.set_index('date', inplace=True)
    
    print("计算连板比率剪刀差...")
    cons_df = calculate_consecutive_scissors(df_stocks)
    cons_df.set_index('date', inplace=True)
    
    print("计算地天板/天地板比率剪刀差...")
    dtb_df = calculate_dtb_tdb_scissors(df_stocks)
    dtb_df.set_index('date', inplace=True)
    
    # 合并数据
    data = data.join(limit_df[['limit_scissors']], how='left')
    data = data.join(cons_df[['consecutive_scissors']], how='left')
    data = data.join(dtb_df[['dtb_tdb_scissors']], how='left')
    
    # 填充缺失值
    data['limit_scissors'] = data['limit_scissors'].fillna(0)
    data['consecutive_scissors'] = data['consecutive_scissors'].fillna(0)
    data['dtb_tdb_scissors'] = data['dtb_tdb_scissors'].fillna(0)
    
    # 推波助澜比率 = 三个指标等权相加
    data['tuibo_ratio'] = (
        data['limit_scissors'] +
        data['consecutive_scissors'] +
        data['dtb_tdb_scissors']
    ) / 3  # 等权平均
    
    # AMA30和AMA100（简单移动平均）
    data['ama30'] = data['tuibo_ratio'].rolling(window=30).mean()
    data['ama100'] = data['tuibo_ratio'].rolling(window=100).mean()
    
    # 做多条件
    data['ama_ratio'] = data['ama30'] / data['ama100']
    data['tb_signal'] = np.where(
        (data['ama_ratio'] > 1.15) &
        (data['ama30'] > 0) &
        (data['ama100'] > 0), 1, 0
    )
    
    return data


def backtest(data):
    """回测"""
    df = data.copy()
    df['daily_return'] = df['close'].pct_change()
    df['position'] = df['tb_signal'].shift(1).fillna(0)
    df['strategy_return'] = df['position'] * df['daily_return']
    
    df['market_nav'] = (1 + df['daily_return']).cumprod()
    df['strategy_nav'] = (1 + df['strategy_return']).cumprod()
    
    df['trade'] = df['position'].diff().abs() > 0
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
        '持仓': int(df['position'].sum()),
        '基准': f"{market_return*100:.2f}%"
    }


def main():
    print("="*60)
    print("推波助澜V3 - 完整实现")
    print("="*60)
    
    df_index, df_stocks, df_limit = load_data()
    print(f"\n数据加载:")
    print(f"  指数: {len(df_index)} 天")
    print(f"  个股: {len(df_stocks)} 条")
    print(f"  涨跌停: {len(df_limit)} 条")
    
    print("\n计算推波助澜V3...")
    data = calculate_tuibo_v3(df_index, df_stocks, df_limit)
    
    print(f"\n信号统计:")
    print(f"  推波助澜做多: {int(data['tb_signal'].sum())} 天")
    
    result = backtest(data)
    metrics = calculate_metrics(result)
    
    print(f"\n" + "="*60)
    print("回测结果 (2023-2026)")
    print("="*60)
    print(f"策略总收益: {metrics['总收益']}")
    print(f"策略年化:   {metrics['年化']}")
    print(f"策略夏普:   {metrics['夏普']}")
    print(f"策略回撤:   {metrics['回撤']}")
    print(f"交易次数:   {metrics['交易']}")
    print(f"持仓天数:   {metrics['持仓']}")
    print(f"\n基准总收益: {metrics['基准']}")


if __name__ == "__main__":
    main()
