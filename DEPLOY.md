# A港股量化平台 - 部署指南

## 1. 环境准备

### 系统要求
- Linux/macOS/Windows (WSL2)
- Docker & Docker Compose
- Python 3.10+

### 安装依赖
```bash
# 安装Python依赖
cd backend && pip install -r requirements.txt
cd ../data-collector && pip install -r requirements.txt
cd ../backtest-engine && pip install -r requirements.txt
```

## 2. 启动基础设施

```bash
cd docker

# 复制环境变量配置
cp .env.example .env

# 启动所有服务
docker-compose up -d

# 查看状态
docker-compose ps
```

服务端口：
- PostgreSQL: 5432
- TimescaleDB: 5433
- Redis: 6379
- MinIO API: 9000
- MinIO Console: 9001
- PgAdmin: 5050

## 3. 初始化数据库

```bash
cd backend
python -c "from main import engine, init_db; init_db(engine)"
```

## 4. 启动数据采集

```bash
cd data-collector

# 初始化股票列表
python collector.py --init

# 全量更新历史数据（首次）
python collector.py --full

# 启动定时调度器（后台运行）
python scheduler.py
```

## 5. 启动后端API

```bash
cd backend
python main.py
```

API文档：http://localhost:8000/docs

## 6. 前端开发（可选）

```bash
cd frontend
npm install
npm run dev
```

## 7. 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                        用户层                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Web UI    │  │   API调用   │  │    Python SDK       │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
└─────────┼────────────────┼────────────────────┼─────────────┘
          │                │                    │
┌─────────▼────────────────▼────────────────────▼─────────────┐
│                      API Gateway                            │
│                    FastAPI (Port 8000)                      │
└─────────┬────────────────┬────────────────────┬─────────────┘
          │                │                    │
    ┌─────▼─────┐    ┌────▼────┐        ┌──────▼──────┐
    │  策略管理  │    │ 回测引擎 │        │  行情查询   │
    └─────┬─────┘    └────┬────┘        └──────┬──────┘
          │               │                     │
┌─────────▼───────────────▼─────────────────────▼─────────────┐
│                      数据层                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  PostgreSQL │  │ TimescaleDB │  │       Redis         │  │
│  │  (用户/策略) │  │  (行情数据)  │  │      (缓存)         │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
          │
    ┌─────▼─────┐
    │  AKShare  │
    │ (数据源)  │
    └───────────┘
```

## 8. 常用命令

```bash
# 查看日志
docker-compose logs -f postgres
docker-compose logs -f timescaledb

# 重启服务
docker-compose restart

# 停止所有服务
docker-compose down

# 删除数据（谨慎）
docker-compose down -v
```

## 9. 配置说明

### 数据库连接
```python
# 主数据库 (PostgreSQL)
DATABASE_URL = "postgresql://quant:quant123@localhost:5432/quant_platform"

# 时序数据库 (TimescaleDB)
TSDB_URL = "postgresql://quant:quant123@localhost:5433/quant_market"
```

### 数据采集配置
```python
# data-collector/collector.py
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://quant:quant@localhost:5432/quant_db")
```

## 10. 开发计划

- [x] 数据库模型设计
- [x] 数据采集模块 (AKShare)
- [x] 后端API (FastAPI)
- [x] 回测引擎 (Backtrader)
- [ ] 前端界面 (React)
- [ ] 任务队列 (Celery)
- [ ] 实时行情推送 (WebSocket)
- [ ] 策略优化/参数调优
- [ ] 机器学习策略支持