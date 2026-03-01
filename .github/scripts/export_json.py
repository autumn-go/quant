#!/usr/bin/env python3
import sqlite3
import json

conn = sqlite3.connect('data-collector/etf_data.db')
conn.row_factory = sqlite3.Row

cursor = conn.execute('''
    SELECT d.ts_code, l.name, d.close, d.pct_chg, d.rsi_6, d.rsi_12, d.rsi_24, d.trade_date
    FROM etf_daily d
    JOIN etf_list l ON d.ts_code = l.ts_code
    WHERE d.rsi_6 < 20
      AND d.trade_date = (SELECT MAX(trade_date) FROM etf_daily)
    ORDER BY d.rsi_6 ASC
''')

rows = cursor.fetchall()
data = []
for row in rows:
    data.append({
        'ts_code': row['ts_code'],
        'name': row['name'] or row['ts_code'],
        'close': round(row['close'], 3),
        'pct_chg': round(row['pct_chg'], 2) if row['pct_chg'] else 0.0,
        'rsi_6': round(row['rsi_6'], 2) if row['rsi_6'] else None,
        'rsi_12': round(row['rsi_12'], 2) if row['rsi_12'] else None,
        'rsi_24': round(row['rsi_24'], 2) if row['rsi_24'] else None,
        'trade_date': row['trade_date']
    })

conn.close()

output = {'total': len(data), 'data': data, 'threshold': 20}
with open('frontend/public/etf_oversold.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f'Exported {len(data)} ETFs')
