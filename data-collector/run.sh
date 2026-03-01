#!/bin/bash
# A股历史数据采集启动脚本

echo "==================================="
echo "A股历史数据采集器"
echo "==================================="
echo ""

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 Python3"
    exit 1
fi

# 安装依赖
echo "[1/4] 检查依赖..."
pip install -q -r requirements.txt

# 创建日志目录
mkdir -p logs

echo ""
echo "请选择操作:"
echo "1) 初始化股票列表（首次运行）"
echo "2) 全量采集2014年以来所有数据"
echo "3) 增量更新（只更新最新数据）"
echo "4) 只采集指数数据"
echo "5) 只采集个股数据"
echo "6) 启动定时调度器"
echo ""
read -p "输入选项 (1-6): " choice

case $choice in
    1)
        echo "[2/4] 初始化股票列表..."
        python3 historical_collector.py --init
        echo ""
        echo "[3/4] 开始全量采集..."
        python3 historical_collector.py --full
        ;;
    2)
        echo "[2/4] 开始全量采集..."
        python3 historical_collector.py --full
        ;;
    3)
        echo "[2/4] 开始增量更新..."
        python3 historical_collector.py --update
        ;;
    4)
        echo "[2/4] 采集指数数据..."
        python3 historical_collector.py --index --full
        ;;
    5)
        echo "[2/4] 采集个股数据..."
        python3 historical_collector.py --stock --full
        ;;
    6)
        echo "[2/4] 启动定时调度器..."
        echo "调度规则:"
        echo "  - 每日 15:30 自动增量更新"
        echo "  - 每周六 02:00 全量检查"
        echo ""
        python3 scheduler.py
        ;;
    *)
        echo "无效选项"
        exit 1
        ;;
esac

echo ""
echo "[4/4] 完成!"
