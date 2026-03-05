#!/usr/bin/env python3
"""
EW-SDM策略回测
策略规则：
1. 从2026年1月6号开始
2. 每天尾盘买入得分前5的行业（等权）
3. 第二天尾盘如果还在前5名榜单就持有，掉出去就卖出
4. 依据当天涨跌幅计算收益，不考虑手续费和滑点
"""

import json
import pandas as pd
import numpy as np
from datetime import datetime
from collections import defaultdict
import matplotlib.pyplot as plt

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'SimHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

def load_data():
    """加载数据"""
    with open('ews_daily_result.json', 'r') as f:
        data = json.load(f)
    return data

def calculate_industry_returns(data):
    """计算每个行业每天的收益率（成分股等权平均）"""
    industry_returns = {}  # {date: {industry_code: return}}
    
    for date, stocks_data in data['stocks_data'].items():
        industry_returns[date] = {}
        for ind_code, stocks_list in stocks_data.items():
            if not stocks_list:
                industry_returns[date][ind_code] = 0
                continue
            # 等权平均涨跌幅
            avg_return = np.mean([s['pct_chg'] for s in stocks_list])
            industry_returns[date][ind_code] = avg_return
    
    return industry_returns

def backtest_ews_strategy(data, industry_returns, start_date='20260106', top_n=5):
    """
    EW-SDM策略回测
    
    规则：
    - 每天尾盘买入当天得分前5的行业（等权）
    - 第二天尾盘检查：如果还在前5就持有，否则卖出
    - 卖出后买入新的前5行业
    """
    dates = sorted(data['daily_data'].keys())
    
    # 找到起始日期索引
    start_idx = 0
    for i, d in enumerate(dates):
        if d >= start_date:
            start_idx = i
            break
    
    # 回测状态
    portfolio = {}  # 当前持有的行业: {industry_code: weight}
    cash = 1.0  # 初始资金归一化为1
    nav_history = []  # 净值历史
    trades = []  # 交易记录
    
    print(f"=== EW-SDM策略回测 ===")
    print(f"起始日期: {dates[start_idx]}")
    print(f"结束日期: {dates[-1]}")
    print(f"每日持仓: 前{top_n}名行业（等权）")
    print(f"调仓规则: 尾盘掉出前{top_n}即卖出，买入新进前{top_n}")
    print("-" * 60)
    
    for i in range(start_idx, len(dates)):
        date = dates[i]
        daily_data = data['daily_data'][date]
        
        # 获取当天前N名行业
        top_industries = set()
        industry_scores = {}
        for item in daily_data[:top_n]:
            top_industries.add(item['industry_code'])
            industry_scores[item['industry_code']] = {
                'name': item['industry_name'],
                'score': item['final_score'],
                'rank': item['rank']
            }
        
        if i == start_idx:
            # 第一天：初始化持仓，买入前5
            weight_per_ind = 1.0 / top_n
            portfolio = {code: weight_per_ind for code in top_industries}
            nav = cash
            print(f"{date} 初始建仓:")
            for code in top_industries:
                name = industry_scores[code]['name']
                score = industry_scores[code]['score']
                print(f"  买入 {name} (得分: {score:.4f})")
        else:
            # 计算当日收益（基于昨日持仓）
            prev_date = dates[i-1]
            daily_return = 0
            
            for ind_code, weight in portfolio.items():
                if ind_code in industry_returns.get(date, {}):
                    ind_return = industry_returns[date][ind_code] / 100  # 转换为小数
                    daily_return += weight * ind_return
            
            cash *= (1 + daily_return)
            nav = cash
            
            # 检查调仓
            current_holdings = set(portfolio.keys())
            to_sell = current_holdings - top_industries  # 掉出前5的
            to_buy = top_industries - current_holdings   # 新进前5的
            
            if to_sell or to_buy:
                # 等权再平衡
                weight_per_ind = 1.0 / top_n
                new_portfolio = {}
                
                # 保留仍在前5的，卖出掉出的
                for code in top_industries:
                    if code in current_holdings:
                        # 继续持有
                        new_portfolio[code] = weight_per_ind
                    else:
                        # 新买入
                        new_portfolio[code] = weight_per_ind
                
                portfolio = new_portfolio
                
                if to_sell:
                    sell_names = [data['daily_data'][date][0]['industry_name']]  # 占位
                    # 找到掉出行业的名称
                    # 从昨天的数据找名称
                
                print(f"{date} 调仓后净值: {nav:.4f}")
                if to_sell:
                    sell_list = list(to_sell)
                    print(f"  卖出: {len(sell_list)}个行业掉出前5")
                if to_buy:
                    buy_list = list(to_buy)
                    print(f"  买入: {len(buy_list)}个行业新进前5")
            else:
                # 无调仓
                pass
        
        nav_history.append({
            'date': date,
            'nav': nav,
            'holdings': list(portfolio.keys()),
            'holdings_count': len(portfolio)
        })
    
    return nav_history, trades

def calculate_metrics(nav_history):
    """计算策略指标"""
    navs = [h['nav'] for h in nav_history]
    dates = [h['date'] for h in nav_history]
    
    # 总收益
    total_return = (navs[-1] - 1) * 100
    
    # 年化收益（假设252个交易日）
    n_days = len(navs)
    annual_return = ((navs[-1] / 1) ** (252 / n_days) - 1) * 100
    
    # 计算日收益率
    daily_returns = []
    for i in range(1, len(navs)):
        daily_returns.append((navs[i] / navs[i-1]) - 1)
    
    # 波动率（年化）
    volatility = np.std(daily_returns) * np.sqrt(252) * 100
    
    # 夏普比率（假设无风险利率2%）
    excess_return = annual_return - 2
    sharpe = excess_return / volatility if volatility > 0 else 0
    
    # 最大回撤
    max_dd = 0
    peak = navs[0]
    for nav in navs:
        if nav > peak:
            peak = nav
        dd = (peak - nav) / peak
        if dd > max_dd:
            max_dd = dd
    
    # 胜率
    win_days = sum(1 for r in daily_returns if r > 0)
    win_rate = win_days / len(daily_returns) * 100 if daily_returns else 0
    
    return {
        'total_return': total_return,
        'annual_return': annual_return,
        'volatility': volatility,
        'sharpe': sharpe,
        'max_drawdown': max_dd * 100,
        'win_rate': win_rate,
        'n_days': n_days,
        'final_nav': navs[-1]
    }

def plot_results(nav_history, metrics):
    """绘制净值曲线"""
    dates = [h['date'] for h in nav_history]
    navs = [h['nav'] for h in nav_history]
    
    # 转换日期格式
    date_labels = [f"{d[:4]}-{d[4:6]}-{d[6:]}" for d in dates]
    
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(range(len(navs)), navs, linewidth=2, color='#2563eb')
    ax.fill_between(range(len(navs)), 1, navs, alpha=0.3, color='#2563eb')
    ax.axhline(y=1, color='gray', linestyle='--', alpha=0.5)
    
    # 设置标题和标签
    ax.set_title('EW-SDM Strategy Backtest', fontsize=14, fontweight='bold')
    ax.set_xlabel('Date', fontsize=11)
    ax.set_ylabel('Net Value', fontsize=11)
    
    # 设置x轴标签（每5个交易日显示一次）
    step = max(1, len(dates) // 10)
    ax.set_xticks(range(0, len(dates), step))
    ax.set_xticklabels([date_labels[i] for i in range(0, len(dates), step)], rotation=45, ha='right')
    
    # 添加指标文本
    textstr = f"""Total Return: {metrics['total_return']:.2f}%
Annual Return: {metrics['annual_return']:.2f}%
Volatility: {metrics['volatility']:.2f}%
Sharpe: {metrics['sharpe']:.2f}
Max Drawdown: {metrics['max_drawdown']:.2f}%
Win Rate: {metrics['win_rate']:.1f}%"""
    
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.8)
    ax.text(0.02, 0.98, textstr, transform=ax.transAxes, fontsize=10,
            verticalalignment='top', bbox=props)
    
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig('ews_backtest_result.png', dpi=150, bbox_inches='tight')
    print("\n图表已保存: ews_backtest_result.png")

def main():
    # 加载数据
    data = load_data()
    
    # 计算行业收益率
    industry_returns = calculate_industry_returns(data)
    
    # 回测
    nav_history, trades = backtest_ews_strategy(data, industry_returns)
    
    # 计算指标
    metrics = calculate_metrics(nav_history)
    
    # 打印结果
    print("\n" + "=" * 60)
    print("回测结果汇总")
    print("=" * 60)
    print(f"回测天数: {metrics['n_days']}")
    print(f"期末净值: {metrics['final_nav']:.4f}")
    print(f"总收益率: {metrics['total_return']:.2f}%")
    print(f"年化收益率: {metrics['annual_return']:.2f}%")
    print(f"年化波动率: {metrics['volatility']:.2f}%")
    print(f"夏普比率: {metrics['sharpe']:.2f}")
    print(f"最大回撤: {metrics['max_drawdown']:.2f}%")
    print(f"胜率: {metrics['win_rate']:.1f}%")
    print("=" * 60)
    
    # 绘制图表
    plot_results(nav_history, metrics)
    
    # 保存详细结果
    result = {
        'metrics': metrics,
        'nav_history': nav_history,
        'strategy': 'EW-SDM Top5 Equal Weight'
    }
    
    with open('ews_backtest_result.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print("详细结果已保存: ews_backtest_result.json")

if __name__ == '__main__':
    main()
