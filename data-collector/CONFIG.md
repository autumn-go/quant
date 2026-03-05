# 2026年A股数据采集配置

## 项目结构

```
quant-gitee/data-collector/
├── collect_2026.py          # 主采集脚本
├── quant_data_2026.db       # 2026年日线数据 (SQLite)
├── push_to_gitee.sh         # Gitee推送脚本
├── daily_update.sh          # 每日增量更新脚本
├── venv/                    # Python虚拟环境
└── logs/                    # 日志目录
```

## 数据采集范围

- **股票数量**: 5485只A股 + 12只主要指数
- **时间范围**: 2026-01-01 至今
- **数据字段**: open, high, low, close, volume, amount
- **数据源**: Tushare Pro API

## 使用说明

### 1. 初始化（首次运行）

```bash
cd data-collector
source venv/bin/activate

# 初始化股票列表
python3 collect_2026.py --init

# 全量采集
python3 collect_2026.py --full
```

### 2. 增量更新

```bash
# 手动执行增量更新
python3 collect_2026.py --update

# 查看统计
python3 collect_2026.py --stats
```

### 3. 推送到 Gitee

```bash
bash push_to_gitee.sh
```

## 定时任务配置

### 方法1: 使用系统 cron

编辑 crontab:
```bash
crontab -e
```

添加以下行（每个交易日 15:35 执行增量更新）:
```
# A股数据每日更新（周一到周五 15:35）
35 15 * * 1-5 /root/.openclaw/workspace/quant-gitee/data-collector/daily_update.sh >> /root/.openclaw/workspace/quant-gitee/data-collector/logs/cron.log 2>&1
```

### 方法2: 使用 OpenClaw Cron

创建定时任务:
```bash
openclaw cron add \
  --name "daily-stock-update" \
  --schedule "0 35 15 * * 1-5" \
  --command "daily_update.sh"
```

## 数据同步到 GitHub

Gitee 支持自动同步到 GitHub 镜像仓库:

1. 在 Gitee 仓库设置中开启 "镜像管理"
2. 绑定 GitHub 仓库
3. 每次推送到 Gitee 后会自动同步到 GitHub

同步延迟: 约 5-10 分钟

## 数据库结构

### stocks 表
```sql
CREATE TABLE stocks (
    symbol TEXT PRIMARY KEY,    -- 股票代码 (000001.SZ)
    code TEXT,                  -- 代码 (000001)
    name TEXT,                  -- 名称
    exchange TEXT,              -- 交易所 (SZ/SH/BJ)
    market TEXT,                -- 市场 (A股/指数)
    list_date TEXT,             -- 上市日期
    industry TEXT               -- 行业
);
```

### daily_prices 表
```sql
CREATE TABLE daily_prices (
    symbol TEXT,                -- 股票代码
    date TEXT,                  -- 交易日期 (YYYYMMDD)
    open REAL,                  -- 开盘价
    high REAL,                  -- 最高价
    low REAL,                   -- 最低价
    close REAL,                 -- 收盘价
    volume REAL,                -- 成交量
    amount REAL,                -- 成交额
    PRIMARY KEY (symbol, date)
);
```

### collection_progress 表
```sql
CREATE TABLE collection_progress (
    symbol TEXT PRIMARY KEY,
    last_date TEXT,             -- 最后更新日期
    status TEXT,                -- 状态
    updated_at TEXT             -- 更新时间
);
```

## 注意事项

1. **API限流**: Tushare 有请求频率限制，脚本已内置 0.05s 间隔
2. **交易日判断**: 每日更新脚本会自动跳过周末
3. **断点续传**: 支持中断后继续从上次位置采集
4. **增量更新**: 只采集缺失的数据，避免重复请求

## 监控与日志

- 采集日志: `logs/collect_2026.log`
- 推送日志: `logs/push.log`
- 每日更新日志: `logs/daily_update.log`

查看实时日志:
```bash
tail -f logs/collect_2026.log
tail -f logs/daily_update.log
```
