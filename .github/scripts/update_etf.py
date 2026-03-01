#!/usr/bin/env python3
import os
import sys
import sqlite3
import pandas as pd
import numpy as np
import tushare as ts

# Setup token and proxy
token = os.getenv('TUSHARE_TOKEN')
if not token:
    print('Error: TUSHARE_TOKEN not set')
    sys.exit(1)

pro = ts.pro_api(token)
pro._DataApi__token = token
pro._DataApi__http_url = 'http://lianghua.nanyangqiankun.top'

# Connect database
conn = sqlite3.connect('data-collector/etf_data.db')

# Get latest date
cursor = conn.execute('SELECT MAX(trade_date) FROM etf_daily')
latest_date = cursor.fetchone()[0]
print(f'DB latest date: {latest_date}')

# Get trade calendar
df_cal = pro.trade_cal(exchange='SSE', start_date=latest_date, end_date='20261231')
trade_dates = df_cal[df_cal['is_open'] == 1]['cal_date'].tolist()

if len(trade_dates) <= 1:
    print('No new trade dates')
    conn.close()
    sys.exit(0)

# Get last 30 trade days
start_date = trade_dates[-30] if len(trade_dates) >= 30 else trade_dates[0]
end_date = trade_dates[-1]
print(f'Update range: {start_date} to {end_date}')

# Get ETF list
cursor = conn.execute('SELECT ts_code FROM etf_list')
etf_codes = [row[0] for row in cursor.fetchall()]
print(f'Total ETFs: {len(etf_codes)}')

# Fetch data
all_data = []
for i, ts_code in enumerate(etf_codes):
    try:
        df = pro.fund_daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
        if df is not None and len(df) > 0:
            all_data.append(df)
        if (i + 1) % 100 == 0:
            print(f'Fetched {i+1}/{len(etf_codes)}')
    except Exception as e:
        print(f'{ts_code} error: {e}')

if all_data:
    df_all = pd.concat(all_data, ignore_index=True)
    df_all = df_all[['ts_code', 'trade_date', 'open', 'high', 'low', 'close', 
                     'pre_close', 'change', 'pct_chg', 'vol', 'amount']]
    
    # Calculate RSI
    def calculate_rsi(prices, period=14):
        if len(prices) < period + 1:
            return [None] * len(prices)
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])
        rsi = []
        for i in range(len(prices)):
            if i < period:
                rsi.append(None)
            elif i == period:
                rsi.append(100 - (100 / (1 + avg_gain/avg_loss)) if avg_loss != 0 else 100)
            else:
                avg_gain = (avg_gain * (period - 1) + gains[i-1]) / period
                avg_loss = (avg_loss * (period - 1) + losses[i-1]) / period
                rsi.append(100 - (100 / (1 + avg_gain/avg_loss)) if avg_loss != 0 else 100)
        return rsi
    
    # Calc RSI for each ETF
    for ts_code in df_all['ts_code'].unique():
        mask = df_all['ts_code'] == ts_code
        closes = df_all.loc[mask, 'close'].values.astype(float)
        df_all.loc[mask, 'rsi_6'] = calculate_rsi(closes, 6)
        df_all.loc[mask, 'rsi_12'] = calculate_rsi(closes, 12)
        df_all.loc[mask, 'rsi_24'] = calculate_rsi(closes, 24)
    
    # Update database
    for _, row in df_all.iterrows():
        conn.execute('''
            INSERT OR REPLACE INTO etf_daily 
            (ts_code, trade_date, open, high, low, close, pre_close, change, pct_chg, vol, amount, rsi_6, rsi_12, rsi_24)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (row['ts_code'], row['trade_date'], row['open'], row['high'], row['low'],
              row['close'], row['pre_close'], row['change'], row['pct_chg'], 
              row['vol'], row['amount'], row.get('rsi_6'), row.get('rsi_12'), row.get('rsi_24')))
    
    conn.commit()
    print(f'Updated {len(df_all)} records')

conn.close()
print('Done')
