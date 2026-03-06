# RRG行业轮动图与EW-SDM情绪加权扩散动量因子策略技术文档

## 目录
1. [策略概述](#1-策略概述)
2. [RRG相对轮动图实现](#2-rrg相对轮动图实现)
3. [EW-SDM情绪加权扩散动量因子实现](#3-ew-sdm情绪加权扩散动量因子实现)
4. [策略数据流与接口](#4-策略数据流与接口)
5. [核心算法详解](#5-核心算法详解)
6. [参数配置与调优](#6-参数配置与调优)
7. [输出结果格式](#7-输出结果格式)
8. [实盘部署指南](#8-实盘部署指南)

---

## 1. 策略概述

### 1.1 策略架构

本策略由两个独立但互补的模块组成：

```
┌─────────────────────────────────────────────────────────────────┐
│                      行业轮动策略系统                             │
├─────────────────────────────┬───────────────────────────────────┤
│      RRG模块                 │          EW-SDM模块               │
│  (strategy_rrg_full.py)      │      (ews_daily_calculator.py)    │
├─────────────────────────────┼───────────────────────────────────┤
│  输入: 同花顺行业指数(90个)   │  输入: 同花顺行业成分股            │
│  基准: 沪深300(000300.SH)    │  涨停数据、封单数据                │
│                             │                                   │
│  核心计算:                   │  核心计算:                         │
│  - RS-Ratio (15日EMA)        │  - 扩散指数(上涨个股占比)          │
│  - RS-Momentum (5日动量)     │  - 情绪权重(涨停连板体系)          │
│                             │  - S-Score(连板情绪杠杆)           │
│  输出:                       │  - 成交额+封单加权                 │
│  - 四象限定位                │                                   │
│  - 历史轨迹数据              │  输出:                             │
│  - 全量行业排名              │  - 行业EW-SDM得分                  │
│                             │  - 成分股明细                      │
└─────────────────────────────┴───────────────────────────────────┘
```

### 1.2 数据依赖

| 数据表 | 来源 | 用途 | 关键字段 |
|--------|------|------|---------|
| `ths_industries` | 同花顺 | 行业基础信息 | ts_code, name |
| `ths_industry_daily` | 同花顺 | 行业指数行情 | ts_code, trade_date, close |
| `ths_industry_members` | 同花顺 | 行业成分股关系 | industry_code, stock_code |
| `daily_prices` | Tushare | 个股日线行情 | symbol, date, close, amount |
| `limit_streaks` | 计算生成 | 涨停连板数据 | ts_code, streak_count, is_broken |
| `limit_list_ths` | 同花顺 | 涨停封单数据 | ts_code, fd_amount |

---

## 2. RRG相对轮动图实现

**实现文件**: `strategy_rrg_full.py`

### 2.1 策略参数配置

```python
PARAMS = {
    'rs_ratio_period': 15,        # RS-Ratio计算周期（15日≈3周）
    'rs_momentum_period': 5,      # RS-Momentum计算周期（5日≈1周）
    'benchmark': '000300.SH',     # 基准指数（沪深300）
}
```

### 2.2 RS-Ratio计算

相对比率衡量行业相对于基准的强势程度：

```python
# 1. 计算原始相对强度
rs = industry_close / benchmark_close

# 2. EMA平滑处理（15日）
rs_ratio_raw = rs.ewm(span=15).mean()

# 3. 基准化到100（以第15日作为基准）
base_ratio = rs_ratio_raw.iloc[15]
rs_ratio = rs_ratio_raw / base_ratio * 100
```

**解读**:
- `RS-Ratio > 100`: 行业相对基准强势
- `RS-Ratio < 100`: 行业相对基准弱势
- 数值偏离100的幅度代表相对强弱程度

### 2.3 RS-Momentum计算

相对动量衡量RS-Ratio的变化趋势，用于预判转折：

```python
# RS-Momentum = 当前RS-Ratio / 5日前RS-Ratio * 100
rs_momentum = rs_ratio / rs_ratio.shift(5) * 100
```

**解读**:
- `RS-Momentum > 100`: RS-Ratio上升，相对强势在增强
- `RS-Momentum < 100`: RS-Ratio下降，相对强势在减弱
- 动量领先于比率变化，提供前瞻性信号

### 2.4 四象限判定

基于100作为分界线：

```python
def _get_quadrant(rs_ratio: float, rs_momentum: float) -> str:
    if rs_ratio > 100 and rs_momentum > 100:
        return 'leading'      # 领先象限：强势且增强
    elif rs_ratio < 100 and rs_momentum > 100:
        return 'improving'    # 改善象限：弱势但改善
    elif rs_ratio < 100 and rs_momentum < 100:
        return 'lagging'      # 落后象限：弱势且恶化
    else:
        return 'weakening'    # 转弱象限：强势但转弱
```

**象限轮动规律**:
```
        improving(改善)  →  leading(领先)
              ↑                ↓
        lagging(落后)   ←  weakening(转弱)
```

### 2.5 输出数据结构

```json
{
  "date": "20260304",
  "start_date": "20260101",
  "benchmark": "000300.SH",
  "params": {
    "rs_ratio_period": 15,
    "rs_momentum_period": 5
  },
  "quadrant_stats": {
    "leading": 12,
    "improving": 23,
    "weakening": 18,
    "lagging": 37
  },
  "all_industries": [
    {
      "date": "20260304",
      "industry_code": "885431.TI",
      "industry_name": "半导体",
      "rs_ratio": 108.52,
      "rs_momentum": 102.34,
      "quadrant": "leading",
      "rank": 1
    }
  ],
  "trails": {
    "885431.TI": {
      "name": "半导体",
      "code": "885431.TI",
      "trail": [
        {"date": "20260102", "rs_ratio": 100.0, "rs_momentum": 100.0, "quadrant": "leading"},
        {"date": "20260103", "rs_ratio": 101.2, "rs_momentum": 101.2, "quadrant": "leading"}
      ]
    }
  }
}
```

---

## 3. EW-SDM情绪加权扩散动量因子实现

**实现文件**: `ews_daily_calculator.py`

### 3.1 策略参数配置

```python
PARAMS = {
    'trend_period': 5,                # 趋势回望期
    'trend_threshold': 3.0,           # 趋势阈值（3%）
    'max_leverage': 2.0,              # S-Score最大杠杆倍数
    'sigmoid_offset': 3.5,            # Sigmoid中心偏移量
    'broken_drop_threshold': -5.0,    # 炸板负反馈跌幅阈值（%）
}
```

### 3.2 情绪权重计算体系

情绪权重是本策略的核心创新，综合考虑涨停状态和涨跌幅：

```python
def calculate_emotion_weight(pct_chg: float, streak: int, is_broken: bool) -> float:
    """
    计算个股情绪权重
    
    规则：
    1. 炸板且跌幅超5% → -1.0（强负反馈）
    2. 无涨停：
       - 涨幅 > 3% → 1.0（主动上涨）
       - 涨幅 ≤ 3% → 0.0（不符合趋势）
    3. 首板 → 1.5
    4. 连板(n≥2) → 1.0 + 0.5 * n
    """
    # 炸板负反馈判定
    if is_broken and pct_chg < PARAMS['broken_drop_threshold']:
        return -1.0
    
    # 无涨停情况
    if streak <= 0:
        return 1.0 if pct_chg > PARAMS['trend_threshold'] else 0.0
    
    # 首板
    if streak == 1:
        return 1.5
    
    # 连板
    return 1.0 + 0.5 * streak
```

**情绪权重对照表**:

| 涨停状态 | 涨跌幅条件 | 情绪权重 | 解读 |
|---------|-----------|---------|------|
| 炸板 | 跌幅<-5% | -1.0 | 强负反馈，资金出逃 |
| 无涨停 | 涨幅>3% | 1.0 | 主动上涨，符合趋势 |
| 无涨停 | 涨幅≤3% | 0.0 | 弱势股，不参与扩散 |
| 首板 | 涨停 | 1.5 | 情绪启动，积极性高 |
| 2连板 | 连续涨停 | 2.0 | 情绪升温 |
| 3连板 | 连续涨停 | 2.5 | 情绪高涨 |
| 4连板+ | 连续涨停 | ≥3.0 | 情绪狂热 |

### 3.3 扩散指数计算

扩散指数反映行业内上涨个股的广度：

```python
# 基础统计
up_ratio = up_count / total_stocks  # 上涨个股占比

# 成交额权重 = 当日成交额 + 封单金额
weight = amount + fd_amount

# 情绪扩散指数（成交额加权）
if total_weight > 0:
    emotion_diff = weighted_emotion / total_weight
    momentum = sum(weighted_returns) / total_weight
```

### 3.4 S-Score连板情绪杠杆

S-Score基于最高连板数计算情绪杠杆系数：

```python
if max_streak <= 0:
    s_score = 1.0  # 无涨停，基准杠杆
else:
    # Sigmoid函数平滑处理
    sigmoid = 1 / (1 + np.exp(-(max_streak - 3.5)))
    s_score = 2.0 * sigmoid + 1
    # 结果范围：max_streak=1时≈1.09，max_streak=4时≈1.91
```

**Sigmoid作用**:
- 平滑连板数的极端影响
- 中心点3.5意味着3-4连板是情绪拐点
- 避免2连板和5连板的杠杆差异过大

### 3.5 EW-SDM最终得分

```python
final_score = momentum * emotion_diff * s_score
```

**三因子分解**:

| 因子 | 含义 | 计算方式 |
|------|------|---------|
| `momentum` | 行业加权涨跌幅 | Σ(权重×涨跌幅)/Σ权重 |
| `emotion_diff` | 情绪扩散指数 | Σ(权重×情绪权重)/Σ权重 |
| `s_score` | 连板情绪杠杆 | 2×sigmoid(max_streak-3.5)+1 |

### 3.6 输出数据结构

```json
{
  "start_date": "20260101",
  "end_date": "20260304",
  "params": {
    "trend_period": 5,
    "trend_threshold": 3.0,
    "max_leverage": 2.0,
    "sigmoid_offset": 3.5,
    "broken_drop_threshold": -5.0
  },
  "daily_data": {
    "20260304": [
      {
        "date": "20260304",
        "industry_code": "885431.TI",
        "industry_name": "半导体",
        "emotion_diff": 0.8234,
        "momentum": 2.4567,
        "s_score": 1.452,
        "final_score": 2.934128,
        "max_streak": 3,
        "limit_up_count": 8,
        "broken_count": 2,
        "total_stocks": 156,
        "up_ratio": 0.6731,
        "rank": 1,
        "detail": "成分股156只, 上涨105只(67.3%), 涨停8只(炸2), 最高3连板"
      }
    ]
  },
  "stocks_data": {
    "20260304": {
      "885431.TI": [
        {
          "ts_code": "688981.SH",
          "name": "中芯国际",
          "pct_chg": 10.02,
          "close": 85.20,
          "streak": 2,
          "is_broken": false,
          "emotion_weight": 2.0
        }
      ]
    }
  }
}
```

---

## 4. 策略数据流与接口

### 4.1 数据库表结构

#### ths_industries（行业基础表）
```sql
CREATE TABLE ths_industries (
    ts_code TEXT PRIMARY KEY,   -- 行业代码，如885431.TI
    name TEXT                   -- 行业名称，如半导体
);
```

#### ths_industry_daily（行业指数日线）
```sql
CREATE TABLE ths_industry_daily (
    ts_code TEXT,
    trade_date TEXT,
    close REAL,
    open REAL,
    high REAL,
    low REAL,
    vol REAL,
    amount REAL,
    PRIMARY KEY (ts_code, trade_date)
);
```

#### ths_industry_members（行业成分股关系）
```sql
CREATE TABLE ths_industry_members (
    industry_code TEXT,   -- 行业代码
    stock_code TEXT,      -- 股票代码
    PRIMARY KEY (industry_code, stock_code)
);
```

#### daily_prices（个股日线）
```sql
CREATE TABLE daily_prices (
    symbol TEXT,
    date TEXT,
    close REAL,
    amount REAL,          -- 成交额
    vol REAL,
    PRIMARY KEY (symbol, date)
);
```

#### limit_streaks（涨停连板数据）
```sql
CREATE TABLE limit_streaks (
    ts_code TEXT,
    trade_date TEXT,
    is_limit_up INTEGER,     -- 是否涨停
    streak_count INTEGER,    -- 连板数
    is_broken INTEGER,       -- 是否炸板
    open_num INTEGER,        -- 开板次数
    pct_chg REAL,            -- 涨跌幅
    industry TEXT,           -- 所属行业
    name TEXT,               -- 股票名称
    PRIMARY KEY (ts_code, trade_date)
);
```

#### limit_list_ths（涨停封单数据）
```sql
CREATE TABLE limit_list_ths (
    ts_code TEXT,
    trade_date TEXT,
    fd_amount REAL,          -- 封单金额
    PRIMARY KEY (ts_code, trade_date)
);
```

### 4.2 RRG策略调用接口

```python
from strategy_rrg_full import RRGStrategy

# 初始化
strategy = RRGStrategy(db_path='data-collector/quant_data.db')

# 运行策略
result = strategy.run(
    start_date='20260101',
    end_date='20260304'
)

# 获取最新信号
latest_signals = result['all_industries']
for signal in latest_signals[:10]:
    print(f"{signal['rank']}. {signal['industry_name']}: "
          f"RS={signal['rs_ratio']:.2f}, "
          f"Mom={signal['rs_momentum']:.2f}, "
          f"象限={signal['quadrant']}")

# 获取行业轨迹
trail = result['trails']['885431.TI']['trail']
```

### 4.3 EW-SDM策略调用接口

```python
from ews_daily_calculator import calculate_ews_for_date
import sqlite3

conn = sqlite3.connect('data-collector/quant_data.db')

# 预加载数据
industries = pd.read_sql('SELECT ts_code, name FROM ths_industries', conn)
members_df = pd.read_sql('SELECT industry_code, stock_code FROM ths_industry_members', conn)

# 计算单日信号
signals = calculate_ews_for_date(
    conn=conn,
    trade_date='20260304',
    industries=industries,
    members_df=members_df,
    daily_map=daily_map,
    prev_map=prev_map,
    limit_map=limit_map,
    fd_map=fd_map
)

# 获取排名前5的行业
top5 = [s for s in signals if s['rank'] <= 5]
```

---

## 5. 核心算法详解

### 5.1 RRG算法流程

```
开始
  │
  ▼
获取行业列表(90个同花顺行业)
  │
  ▼
对每个行业:
  ├─ 获取行业指数日线数据
  ├─ 获取沪深300基准数据
  ├─ 对齐日期
  │
  ▼
计算RS-Ratio:
  ├─ industry_close / benchmark_close → rs
  ├─ rs.ewm(span=15).mean() → rs_ratio_raw
  └─ rs_ratio_raw / base * 100 → rs_ratio
  │
  ▼
计算RS-Momentum:
  └─ rs_ratio / rs_ratio.shift(5) * 100 → rs_momentum
  │
  ▼
判定象限(基于100分界线)
  │
  ▼
保存历史轨迹
  │
  ▼
按RS-Ratio排序生成排名
  │
  ▼
输出JSON结果
```

### 5.2 EW-SDM算法流程

```
开始
  │
  ▼
获取交易日列表
  │
  ▼
对每个交易日:
  ├─ 加载当日个股行情
  ├─ 加载涨停/连板数据
  ├─ 加载封单数据
  └─ 加载前一日收盘价
  │
  ▼
对每个行业:
  ├─ 获取成分股列表
  │
  ▼
  对每只股票:
    ├─ 计算涨跌幅
    ├─ 判定趋势状态
    ├─ 获取涨停信息(连板数/炸板)
    ├─ 计算情绪权重
    ├─ 计算权重(成交额+封单)
    └─ 累加统计量
  │
  ▼
计算行业指标:
  ├─ up_ratio = 上涨股数 / 总股数
  ├─ emotion_diff = 加权情绪权重和 / 总权重
  ├─ momentum = 加权涨跌幅和 / 总权重
  ├─ max_streak = 最高连板数
  └─ s_score = 2 * sigmoid(max_streak-3.5) + 1
  │
  ▼
计算最终得分:
  └─ final_score = momentum * emotion_diff * s_score
  │
  ▼
行业排序，生成排名
  │
  ▼
生成成分股明细
  │
  ▼
输出JSON结果
```

### 5.3 关键计算细节

#### EMA平滑公式

```python
# pandas ewm使用指数加权移动平均
# 衰减系数α = 2 / (span + 1)
# 对于span=15，α = 2/16 = 0.125

rs_ratio_raw = rs.ewm(span=15).mean()
```

#### Sigmoid函数

```python
sigmoid(x) = 1 / (1 + e^(-x))

# 当x=0时，sigmoid=0.5
# 当x=3.5时，sigmoid≈0.97
# 当x=-3.5时，sigmoid≈0.03

# 应用到s_score:
s_score = 2 * sigmoid(max_streak - 3.5) + 1

# max_streak=1: s_score ≈ 2*0.075 + 1 = 1.15
# max_streak=3: s_score ≈ 2*0.5 + 1 = 2.0  
# max_streak=5: s_score ≈ 2*0.982 + 1 = 2.96
```

---

## 6. 参数配置与调优

### 6.1 RRG参数影响

| 参数 | 默认值 | 调小影响 | 调大影响 |
|------|-------|---------|---------|
| rs_ratio_period | 15日 | 更敏感，噪音多 | 更平滑，滞后大 |
| rs_momentum_period | 5日 | 短期动量敏感 | 长期趋势捕捉 |

**推荐组合**:
- 激进型: (10, 3) - 更快捕捉转折
- 稳健型: (15, 5) - 平衡灵敏度与稳定性
- 保守型: (20, 10) - 过滤短期噪音

### 6.2 EW-SDM参数影响

| 参数 | 默认值 | 调小影响 | 调大影响 |
|------|-------|---------|---------|
| trend_threshold | 3% | 更多股票参与 | 更严格筛选 |
| max_leverage | 2.0 | 杠杆效应弱 | 连板影响放大 |
| sigmoid_offset | 3.5 | 更早启动杠杆 | 更晚启动杠杆 |
| broken_drop_threshold | -5% | 更多负反馈 | 仅极端炸板 |

### 6.3 参数敏感性测试

建议定期执行的回测验证：

```python
def parameter_sensitivity_test():
    """参数敏感性测试"""
    param_grid = {
        'rs_ratio_period': [10, 15, 20],
        'rs_momentum_period': [3, 5, 10],
        'trend_threshold': [2.0, 3.0, 5.0],
        'sigmoid_offset': [2.5, 3.5, 4.5]
    }
    
    results = []
    for params in grid_search(param_grid):
        result = backtest(params)
        results.append({
            'params': params,
            'sharpe': result.sharpe_ratio,
            'max_drawdown': result.max_drawdown,
            'annual_return': result.annual_return
        })
    
    return optimal_params
```

---

## 7. 输出结果格式

### 7.1 RRG输出文件: `rrg_full_result.json`

```json
{
  "metadata": {
    "date": "20260304",
    "start_date": "20260101",
    "benchmark": "000300.SH",
    "params": {
      "rs_ratio_period": 15,
      "rs_momentum_period": 5
    }
  },
  "summary": {
    "quadrant_stats": {
      "leading": 12,      // 领先象限数量
      "improving": 23,    // 改善象限数量
      "weakening": 18,    // 转弱象限数量
      "lagging": 37       // 落后象限数量
    },
    "total_industries": 90
  },
  "rankings": [
    {
      "rank": 1,
      "industry_code": "885431.TI",
      "industry_name": "半导体",
      "rs_ratio": 108.52,
      "rs_momentum": 102.34,
      "quadrant": "leading"
    }
  ],
  "trails": {
    "885431.TI": {
      "name": "半导体",
      "trail": [
        {
          "date": "20260102",
          "rs_ratio": 100.0,
          "rs_momentum": 100.0,
          "quadrant": "leading"
        }
      ]
    }
  }
}
```

### 7.2 EW-SDM输出文件: `ews_daily_result.json`

```json
{
  "metadata": {
    "start_date": "20260101",
    "end_date": "20260304",
    "params": {
      "trend_period": 5,
      "trend_threshold": 3.0,
      "max_leverage": 2.0,
      "sigmoid_offset": 3.5,
      "broken_drop_threshold": -5.0
    }
  },
  "daily_signals": {
    "20260304": [
      {
        "date": "20260304",
        "industry_code": "885431.TI",
        "industry_name": "半导体",
        "emotion_diff": 0.8234,       // 情绪扩散指数
        "momentum": 2.4567,            // 动量因子
        "s_score": 1.452,              // 连板杠杆系数
        "final_score": 2.934128,       // EW-SDM最终得分
        "max_streak": 3,               // 最高连板数
        "limit_up_count": 8,           // 涨停家数
        "broken_count": 2,             // 炸板家数
        "total_stocks": 156,           // 成分股总数
        "up_ratio": 0.6731,            // 上涨比例
        "rank": 1,                     // 排名
        "detail": "成分股156只, 上涨105只(67.3%), 涨停8只(炸2), 最高3连板"
      }
    ]
  },
  "stocks_detail": {
    "20260304": {
      "885431.TI": [
        {
          "ts_code": "688981.SH",
          "name": "中芯国际",
          "pct_chg": 10.02,
          "close": 85.20,
          "streak": 2,
          "is_broken": false,
          "emotion_weight": 2.0
        }
      ]
    }
  }
}
```

---

## 8. 实盘部署指南

### 8.1 每日运行流程

```bash
#!/bin/bash
# run_daily.sh

cd /root/.openclaw/workspace/quant-main

# 1. 更新数据
cd data-collector
python data_collector.py --update

# 2. 更新涨停数据
cd ..
python update_limit_streaks.py

# 3. 计算RRG
python strategy_rrg_full.py --start $(date +%Y%m%d) --end $(date +%Y%m%d)

# 4. 计算EW-SDM
python ews_daily_calculator.py

# 5. 生成交易信号
python generate_signals.py
```

### 8.2 信号使用建议

#### RRG信号解读

| 象限 | 操作建议 | 优先级 |
|------|---------|-------|
| leading | 持有，享受趋势 | P0 |
| improving | 关注，准备布局 | P1 |
| weakening | 警惕，逐步减仓 | P2 |
| lagging | 回避 | P3 |

**关键信号**:
- `improving` → `leading`: 加仓信号
- `leading` → `weakening`: 减仓信号
- 连续多日在`weakening`: 清仓信号

#### EW-SDM信号解读

| final_score | 操作建议 |
|------------|---------|
| >3.0 | 强烈推荐，情绪高涨 |
| 1.5~3.0 | 推荐，积极配置 |
| 0~1.5 | 中性，小仓位配置 |
| <0 | 回避，负面情绪 |

### 8.3 组合使用建议

**强买入信号** (同时满足):
- RRG在`leading`或刚进入`leading`
- EW-SDM排名Top 5
- final_score > 2.0

**卖出信号** (任一满足):
- RRG从`leading`进入`weakening`
- EW-SDM排名连续3日下降
- 行业出现大面积炸板(broken_count > limit_up_count * 0.3)

### 8.4 风险控制

1. **仓位控制**: 单行业不超过20%
2. **止损线**: 单个行业亏损>8%强制减仓
3. **情绪过热**: 当S-Score > 2.5时，降低仓位至50%
4. **流动性**: 排除日成交额<1亿的成分股占比>30%的行业

---

## 附录

### A. 同花顺行业代码示例

| 行业代码 | 行业名称 |
|---------|---------|
| 885431.TI | 半导体 |
| 885432.TI | 元器件 |
| 885433.TI | 通信设备 |
| 885434.TI | 电信运营 |
| 885452.TI | 软件服务 |
| 885453.TI | 互联网 |
| 885454.TI | 传媒娱乐 |
| 885456.TI | 汽车类 |
| 885458.TI | 电气设备 |
| 885459.TI | 工程机械 |

### B. 异常处理

| 异常场景 | 处理方式 |
|---------|---------|
| 行业指数数据缺失 | 跳过该行业，记录日志 |
| 成分股全部停牌 | emotion_diff=0, momentum=0 |
| 涨停数据缺失 | streak=0, is_broken=False |
| 除权除息 | 使用前复权价格 |

### C. 版本历史

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v1.0 | 2026-01-01 | 初始版本，基础RRG |
| v2.0 | 2026-02-01 | 增加EW-SDM模块 |
| v3.0 | 2026-02-15 | 修复炸板负反馈逻辑 |
| v4.0 | 2026-03-01 | 增加封单金额加权 |
| v5.0 | 2026-03-05 | 修正阈值比较Bug，优化情绪权重 |

---

*文档版本：v5.0*  
*最后更新：2026-03-06*  
*基于代码版本：ews_daily_calculator.py v5 + strategy_rrg_full.py*
