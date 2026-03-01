"""
ETF 数据 API 路由
提供ETF超跌数据查询接口
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import sqlite3
import os

router = APIRouter(prefix="/api/etf", tags=["ETF数据"])

# 数据库路径
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data-collector", "etf_data.db")


class ETFOversoldItem(BaseModel):
    ts_code: str
    name: str
    close: float
    pct_chg: float
    rsi_6: float
    rsi_12: float
    rsi_24: float
    trade_date: str


class ETFOversoldResponse(BaseModel):
    total: int
    data: List[ETFOversoldItem]
    threshold: float


def get_db_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@router.get("/oversold", response_model=ETFOversoldResponse)
async def get_oversold_etfs(
    rsi_threshold: float = 20.0,
    rsi_period: str = "rsi_6",
    limit: int = 50
):
    """
    获取超跌ETF列表
    
    参数:
    - rsi_threshold: RSI阈值，默认20
    - rsi_period: RSI周期，可选 rsi_6, rsi_12, rsi_24
    - limit: 返回数量限制
    """
    try:
        conn = get_db_connection()
        
        # 验证rsi_period参数
        valid_periods = ["rsi_6", "rsi_12", "rsi_24"]
        if rsi_period not in valid_periods:
            rsi_period = "rsi_6"
        
        # 查询超跌ETF
        query = f"""
        SELECT 
            d.ts_code,
            l.name,
            d.close,
            d.pct_chg,
            d.rsi_6,
            d.rsi_12,
            d.rsi_24,
            d.trade_date
        FROM etf_daily d
        JOIN etf_list l ON d.ts_code = l.ts_code
        WHERE d.{rsi_period} < ?
          AND d.trade_date = (
              SELECT MAX(trade_date) FROM etf_daily
          )
        ORDER BY d.{rsi_period} ASC
        LIMIT ?
        """
        
        cursor = conn.execute(query, (rsi_threshold, limit))
        rows = cursor.fetchall()
        conn.close()
        
        # 转换为响应模型
        data = []
        for row in rows:
            data.append(ETFOversoldItem(
                ts_code=row["ts_code"],
                name=row["name"] or row["ts_code"],  # 如果没有名称，使用代码
                close=round(row["close"], 3),
                pct_chg=round(row["pct_chg"], 2) if row["pct_chg"] else 0.0,
                rsi_6=round(row["rsi_6"], 2) if row["rsi_6"] else None,
                rsi_12=round(row["rsi_12"], 2) if row["rsi_12"] else None,
                rsi_24=round(row["rsi_24"], 2) if row["rsi_24"] else None,
                trade_date=row["trade_date"]
            ))
        
        return ETFOversoldResponse(
            total=len(data),
            data=data,
            threshold=rsi_threshold
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/stats")
async def get_etf_stats():
    """获取ETF统计信息"""
    try:
        conn = get_db_connection()
        
        # 统计信息
        stats = {}
        
        # ETF总数
        cursor = conn.execute("SELECT COUNT(*) FROM etf_list")
        stats["total_etfs"] = cursor.fetchone()[0]
        
        # 有数据的ETF数量
        cursor = conn.execute("SELECT COUNT(DISTINCT ts_code) FROM etf_daily")
        stats["etfs_with_data"] = cursor.fetchone()[0]
        
        # 日线数据总数
        cursor = conn.execute("SELECT COUNT(*) FROM etf_daily")
        stats["total_records"] = cursor.fetchone()[0]
        
        # 最新日期
        cursor = conn.execute("SELECT MAX(trade_date) FROM etf_daily")
        stats["latest_date"] = cursor.fetchone()[0]
        
        # 超跌ETF数量 (RSI < 20)
        cursor = conn.execute("""
            SELECT COUNT(*) FROM etf_daily
            WHERE rsi_6 < 20
              AND trade_date = (SELECT MAX(trade_date) FROM etf_daily)
        """)
        stats["oversold_count"] = cursor.fetchone()[0]
        
        # 极度超卖数量 (RSI < 10)
        cursor = conn.execute("""
            SELECT COUNT(*) FROM etf_daily
            WHERE rsi_6 < 10
              AND trade_date = (SELECT MAX(trade_date) FROM etf_daily)
        """)
        stats["extreme_oversold_count"] = cursor.fetchone()[0]
        
        conn.close()
        
        return stats
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/{ts_code}/history")
async def get_etf_history(ts_code: str, limit: int = 60):
    """
    获取单只ETF历史数据
    
    参数:
    - ts_code: ETF代码，如 510050.SH
    - limit: 返回天数，默认60天
    """
    try:
        conn = get_db_connection()
        
        query = """
        SELECT 
            trade_date,
            open,
            high,
            low,
            close,
            pct_chg,
            rsi_6,
            rsi_12,
            rsi_24,
            vol,
            amount
        FROM etf_daily
        WHERE ts_code = ?
        ORDER BY trade_date DESC
        LIMIT ?
        """
        
        cursor = conn.execute(query, (ts_code, limit))
        rows = cursor.fetchall()
        conn.close()
        
        data = []
        for row in rows:
            data.append({
                "trade_date": row["trade_date"],
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "pct_chg": row["pct_chg"],
                "rsi_6": row["rsi_6"],
                "rsi_12": row["rsi_12"],
                "rsi_24": row["rsi_24"],
                "vol": row["vol"],
                "amount": row["amount"]
            })
        
        return {
            "ts_code": ts_code,
            "total": len(data),
            "data": data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")
