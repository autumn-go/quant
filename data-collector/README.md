# 数据采集使用说明

## 快速开始

```bash
cd data-collector

# 交互式启动
./run.sh

# 或直接运行
python historical_collector.py --init    # 初始化
python historical_collector.py --full    # 全量采集
python historical_collector.py --update  # 增量更新
```

## 功能特性

- **2014年以来全量数据**: 所有A股、指数、ETF日线数据
- **前复权处理**: 自动处理分红送股
- **断点续传**: 支持中断后从上次位置继续
- **增量更新**: 只采集新数据，避免重复
- **多线程加速**: 5并发线程 + 限速保护
- **TimescaleDB**: 时序数据库优化存储

## 数据范围

| 类型 | 数量 | 说明 |
|------|------|------|
| A股个股 | ~5000+ | 沪/深/北交所全部股票 |
| 指数 | 10+ | 上证、深证、创业板等主要指数 |
| 时间跨度 | 2014-至今 | 约10年历史数据 |

## 存储结构

```
PostgreSQL + TimescaleDB
├── stocks (股票基础信息)
│   ├── symbol: 代码 (000001.SZ)
│   ├── name: 名称
│   ├── market: 市场 (A股/港股)
│   └── exchange: 交易所 (SZ/SH/BJ)
│
└── daily_prices (日线数据 - hypertable)
    ├── time: 日期
    ├── stock_id: 关联stocks
    ├── open/high/low/close: 价格
    ├── volume: 成交量
    └── amount: 成交额
```

## 定时任务

```bash
# 启动后台调度器
python scheduler.py

# 调度规则
每日 15:30  - 增量更新当日数据
每周六 02:00 - 全量数据检查
```

## 性能预估

- **首次全量采集**: 约2-4小时（5000+股票 × 10年）
- **每日增量更新**: 约5-10分钟
- **存储占用**: 约5-10GB（全部历史数据）

## 注意事项

1. AKShare数据源免费，但请控制请求频率
2. 首次运行建议先 `--init` 初始化股票列表
3. 数据库需提前配置好 TimescaleDB 扩展
4. 日志保存在 `logs/` 目录
