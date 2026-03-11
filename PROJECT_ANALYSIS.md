# Quant 量化交易平台 - 项目分析总结

## 项目概述

这是一个**A股/港股量化跟踪与回测平台**，基于 FastAPI + React + AKShare 构建。

**仓库地址**: https://gitee.com/autumn-go/quant  
**本地路径**: `/root/.openclaw/workspace/quant-main`

---

## 项目结构

```
quant-main/
├── backend/              # FastAPI 后端服务
│   ├── main.py          # 主服务入口，提供RESTful API
│   ├── schemas.py       # Pydantic 数据模型
│   ├── routers/         # API路由模块
│   └── requirements.txt # 后端依赖
├── data-collector/      # 数据采集模块 (AKShare)
│   ├── collector.py     # 主采集器
│   ├── collect_stock_daily.py  # 日线数据采集
│   ├── industry_collector.py   # 行业数据采集
│   └── scheduler.py     # 定时任务调度
├── backtest-engine/     # 回测引擎 (Backtrader)
│   └── engine.py        # 回测引擎实现
├── frontend/            # React + TypeScript 前端
│   ├── src/
│   │   ├── pages/       # 页面组件
│   │   ├── components/  # 公共组件
│   │   └── api/         # API调用
│   └── package.json
├── shared/              # 共享模型
│   ├── models.py        # SQLAlchemy ORM模型
│   └── models_sqlite.py # SQLite版本模型
├── docker/              # Docker配置
│   ├── docker-compose.yml
│   └── init/            # 数据库初始化脚本
├── data/                # 数据文件
└── *.py                 # 独立策略脚本
```

---

## 核心功能模块

### 1. 数据采集 (data-collector/)
- **A股数据采集**: 沪深京三市股票日线、复权数据
- **港股数据采集**: 港股通成分股数据
- **行业数据**: 同花顺行业分类及成分股
- **定时调度**: 支持每日自动更新

**主要文件**:
- `collector.py` - 主采集器，支持股票列表初始化、全量/增量更新
- `collect_stock_daily.py` - 日线数据采集
- `industry_collector.py` - 行业数据采集
- `scheduler.py` - 定时任务调度器

### 2. 后端API (backend/)
- **FastAPI** 框架，自动生成API文档
- **认证授权**: JWT Token认证
- **股票数据接口**: 股票列表、个股信息、历史价格
- **策略管理**: 策略CRUD、回测任务管理

**主要文件**:
- `main.py` - 主服务，端口8000
- `schemas.py` - Pydantic模型定义
- `routers/backtest.py` - 回测相关API

### 3. 回测引擎 (backtest-engine/)
- **Backtrader** 框架
- 支持自定义策略
- 绩效分析、风险指标计算

### 4. 策略模块

#### 扩散动量因子策略 (`strategy_diffusion_momentum.py`)
- 基于国海证券研报实现
- 参数：30日趋势判定，3%阈值
- 输出：扩散动量因子排名

#### RRG相对轮动图策略 (`strategy_rrg_full.py`)
- RS-Ratio + RS-Momentum 计算
- 四象限分类（领先/改善/落后/衰退）
- 支持历史轨迹计算

#### EWS早预警系统 (`ews_daily_calculator.py`)
- ETF超卖检测
- 多指标综合评分

#### SDM策略 (`sdm_daily_calculator.py`)
- 行业扩散动量日度计算

---

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | FastAPI + SQLAlchemy + Pydantic |
| 数据库 | PostgreSQL + TimescaleDB (时序) / SQLite |
| 缓存 | Redis |
| 数据采集 | AKShare + Tushare |
| 回测 | Backtrader |
| 前端 | React + TypeScript + Ant Design + ECharts |
| 部署 | Docker Compose |

---

## 数据库模型

### 核心表结构

1. **stocks** - 股票基础信息
   - symbol, code, name, market, exchange, industry

2. **daily_prices** - 日线行情（时序表）
   - time, stock_id, open, high, low, close, volume, amount
   - MA5, MA10, MA20 预计算

3. **ths_industries** - 同花顺行业
   - ts_code, name, type

4. **ths_industry_members** - 行业成分股
   - industry_code, stock_code

5. **users** - 用户管理
   - username, email, hashed_password

6. **strategies** - 策略管理
   - name, description, code, owner_id

---

## 安装依赖

项目所需的主要Python包：

```bash
# 后端依赖
pip install fastapi uvicorn sqlalchemy psycopg2-binary pydantic redis \
    python-jose passlib pandas numpy backtrader loguru

# 数据采集依赖
pip install akshare schedule tenacity tqdm

# 回测引擎依赖
pip install matplotlib
```

**注意**: 项目当前没有使用 Ta-lib，技术指标通过 pandas/numpy 计算。

---

## 运行方式

### 1. 启动基础设施
```bash
cd docker
cp .env.example .env
docker-compose up -d
```

### 2. 初始化数据库
```bash
cd backend
python -c "from main import engine, init_db; init_db(engine)"
```

### 3. 启动数据采集
```bash
cd data-collector
python collector.py --init      # 初始化股票列表
python collector.py --full      # 全量更新
python scheduler.py             # 启动定时调度
```

### 4. 启动后端服务
```bash
cd backend
python main.py
# API文档: http://localhost:8000/docs
```

### 5. 启动前端（可选）
```bash
cd frontend
npm install
npm run dev
```

---

## 独立策略运行

```bash
# RRG策略
cd /root/.openclaw/workspace/quant-main
python strategy_rrg_full.py

# 扩散动量策略
python strategy_diffusion_momentum.py

# EWS早预警
python ews_daily_calculator.py
```

---

## 待办事项 (TODO.md)

- [ ] 采集全部5485只股票（预计4-5小时）
- [ ] 采集指数数据（上证、沪深300等）
- [ ] 开发回测功能

---

## Git配置

- **用户名**: autumn-go
- **远程仓库**: https://gitee.com/autumn-go/quant.git
- **Token**: e03a9e227029339114cb9de9300a4140

### 推送代码
```bash
cd /root/.openclaw/workspace/quant-main
git add -A
git commit -m "更新描述"
git push origin main
```

---

## 文件统计

- Python文件: ~40个
- 前端组件: ~15个
- 配置文件: ~10个
- 总代码行数: ~8000+ 行

---

**分析完成时间**: 2026-03-05
**分析人**: Kimi Claw
