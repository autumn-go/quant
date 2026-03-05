#!/usr/bin/env python3
"""
数据采集进度监控脚本
"""

import sqlite3
import os
import subprocess
from datetime import datetime

DB_PATH = "/root/.openclaw/workspace/quant-platform/data-collector/quant_data.db"
LOG_PATH = "/root/.openclaw/workspace/quant-platform/data-collector/logs/full_collection.log"

def check_progress():
    """检查采集进度"""
    
    # 检查进程状态
    result = subprocess.run(
        ["ps", "aux"],
        capture_output=True, text=True
    )
    is_running = "tushare_historical.py --full" in result.stdout
    
    # 获取数据库统计
    conn = sqlite3.connect(DB_PATH)
    
    cursor = conn.execute('SELECT COUNT(*) FROM stocks')
    total_stocks = cursor.fetchone()[0]
    
    cursor = conn.execute('SELECT COUNT(DISTINCT symbol) FROM daily_prices')
    collected_symbols = cursor.fetchone()[0]
    
    cursor = conn.execute('SELECT COUNT(*) FROM daily_prices')
    total_records = cursor.fetchone()[0]
    
    cursor = conn.execute('SELECT market, COUNT(*) FROM stocks GROUP BY market')
    market_stats = dict(cursor.fetchall())
    
    conn.close()
    
    # 计算进度
    progress_pct = (collected_symbols / total_stocks * 100) if total_stocks > 0 else 0
    
    # 读取最新日志
    last_log_lines = []
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH, 'r') as f:
            lines = f.readlines()
            last_log_lines = lines[-10:] if len(lines) > 10 else lines
    
    # 生成报告
    report = f"""
{'='*60}
量化数据采集进度报告 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*60}

进程状态: {'运行中' if is_running else '已停止'}

数据库统计:
  - 股票总数: {total_stocks}
  - 已采集标的: {collected_symbols}
  - 总记录数: {total_records:,}
  - 完成进度: {progress_pct:.2f}%

市场分布:
  - A股: {market_stats.get('A股', 0)} 只
  - 指数: {market_stats.get('指数', 0)} 个

最新日志 (最后10行):
"""
    for line in last_log_lines:
        report += f"  {line.rstrip()}\n"
    
    report += "="*60 + "\n"
    
    return report

if __name__ == "__main__":
    print(check_progress())
