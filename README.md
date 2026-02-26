# A港股量化跟踪与回测平台

## 项目结构

```
quant-platform/
├── backend/           # FastAPI 主服务
├── data-collector/    # AKShare 数据采集
├── backtest-engine/   # 回测引擎
├── frontend/          # React 前端
├── shared/            # 共享模型、工具
├── docker/            # Docker 配置
└── docker-compose.yml
```

## 快速启动

```bash
# 1. 启动基础设施
docker-compose up -d

# 2. 安装依赖
cd backend && pip install -r requirements.txt
cd ../data-collector && pip install -r requirements.txt

# 3. 初始化数据库
python backend/scripts/init_db.py

# 4. 启动服务
python backend/main.py
python data-collector/scheduler.py
```

## 技术栈

- **后端**: FastAPI + SQLAlchemy + Pydantic
- **数据库**: PostgreSQL + TimescaleDB
- **缓存**: Redis
- **数据采集**: AKShare
- **回测**: Backtrader + 自研扩展
- **前端**: React + Ant Design + ECharts
- **部署**: Docker Compose

## 功能模块

1. **行情数据**: A股/港股日线、复权、财务数据
2. **策略管理**: Python策略编写、版本控制
3. **回测引擎**: 事件驱动回测、绩效分析
4. **实时监控**: 策略信号、持仓跟踪
5. **可视化**: K线图、收益曲线、风险指标