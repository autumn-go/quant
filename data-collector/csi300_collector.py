"""
沪深300指数数据采集器
采集内容：
1. 沪深300指数日K线数据（2025年至今）
2. 沪深300成分股列表及权重
3. 成分股日K线数据（2025年至今）
4. 每日涨跌停数据（2025年至今）

使用AKShare数据源，数据存储在SQLite数据库中
"""

import akshare as ak
import pandas as pd
import sqlite3
import os
from datetime import datetime, timedelta
from typing import List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential
import time

# 数据库路径
DB_PATH = os.path.join(os.path.dirname(__file__), 'csi300_data.db')

# 起始日期（2025年1月1日）
START_DATE = '20250101'
END_DATE = datetime.now().strftime('%Y%m%d')


class CSI300Collector:
    """沪深300数据采集器"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self._init_db()
    
    def _init_db(self):
        """初始化数据库表结构"""
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        
        # 1. 沪深300指数日K线
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS csi300_index_daily (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                amount REAL,
                amplitude REAL,
                pct_change REAL,
                change REAL,
                turnover_rate REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(date)
            )
        ''')
        
        # 2. 沪深300成分股列表及权重
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS csi300_constituents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                name TEXT,
                weight REAL,
                date TEXT NOT NULL,
                exchange TEXT,
                industry TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(code, date)
            )
        ''')
        
        # 3. 成分股日K线数据
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS csi300_stock_daily (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                code TEXT NOT NULL,
                date TEXT NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                amount REAL,
                amplitude REAL,
                pct_change REAL,
                change REAL,
                turnover_rate REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, date)
            )
        ''')
        
        # 4. 每日涨跌停数据
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS limit_up_down (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                code TEXT NOT NULL,
                name TEXT,
                close REAL,
                pct_change REAL,
                turnover_rate REAL,
                limit_type TEXT,  -- 'up' 涨停, 'down' 跌停
                amount REAL,
                industry TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(date, code)
            )
        ''')
        
        # 创建索引
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_csi300_daily_date ON csi300_index_daily(date)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_constituents_code ON csi300_constituents(code)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_stock_daily_symbol ON csi300_stock_daily(symbol)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_stock_daily_date ON csi300_stock_daily(date)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_limit_date ON limit_up_down(date)')
        
        self.conn.commit()
        print(f"✓ 数据库初始化完成: {self.db_path}")
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
    
    # ==================== 1. 采集沪深300指数日K线 ====================
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def fetch_csi300_index_daily(self, start_date: str = START_DATE, end_date: str = END_DATE) -> pd.DataFrame:
        """采集沪深300指数日K线数据"""
        print(f"\n[1/4] 采集沪深300指数日K线数据 ({start_date} - {end_date})...")
        
        # 使用AKShare获取指数历史行情
        df = ak.index_zh_a_hist(symbol="000300", period="daily", 
                                 start_date=start_date, end_date=end_date)
        
        if df.empty:
            print("  ⚠ 无数据返回")
            return df
        
        # 标准化列名
        df.columns = ['date', 'open', 'close', 'high', 'low', 'volume',
                     'amount', 'amplitude', 'pct_change', 'change', 'turnover']
        df['date'] = df['date'].astype(str).str.replace('-', '')
        
        print(f"  ✓ 获取到 {len(df)} 条指数数据")
        return df
    
    def save_csi300_index_daily(self, df: pd.DataFrame):
        """保存指数日K线数据"""
        if df.empty:
            return
        
        for _, row in df.iterrows():
            self.cursor.execute('''
                INSERT OR REPLACE INTO csi300_index_daily 
                (date, open, high, low, close, volume, amount, amplitude, pct_change, change, turnover_rate)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (row['date'], row['open'], row['high'], row['low'], row['close'],
                  row['volume'], row['amount'], row['amplitude'], 
                  row['pct_change'], row['change'], row['turnover']))
        
        self.conn.commit()
        print(f"  ✓ 保存了 {len(df)} 条指数数据到数据库")
    
    # ==================== 2. 采集沪深300成分股及权重 ====================
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def fetch_csi300_constituents(self) -> pd.DataFrame:
        """采集沪深300成分股及权重"""
        print(f"\n[2/4] 采集沪深300成分股及权重...")
        
        # 获取最新成分股列表
        df = ak.index_stock_cons_weight_csindex(symbol="000300")
        
        if df.empty:
            print("  ⚠ 无成分股数据")
            return df
        
        # 标准化列名
        df = df.rename(columns={
            '成分券代码': 'code',
            '成分券名称': 'name',
            '权重': 'weight',
            '交易所': 'exchange',
            '日期': 'date'
        })
        
        # 处理日期格式
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y%m%d')
        else:
            df['date'] = END_DATE
        
        print(f"  ✓ 获取到 {len(df)} 只成分股")
        return df
    
    def save_csi300_constituents(self, df: pd.DataFrame):
        """保存成分股列表"""
        if df.empty:
            return
        
        for _, row in df.iterrows():
            self.cursor.execute('''
                INSERT OR REPLACE INTO csi300_constituents 
                (code, name, weight, date, exchange, industry)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (row['code'], row['name'], row.get('weight', 0), 
                  row['date'], row.get('exchange', ''), row.get('industry', '')))
        
        self.conn.commit()
        print(f"  ✓ 保存了 {len(df)} 只成分股到数据库")
    
    def get_constituent_symbols(self) -> List[str]:
        """获取数据库中的成分股代码列表"""
        self.cursor.execute('SELECT DISTINCT code FROM csi300_constituents')
        return [row[0] for row in self.cursor.fetchall()]
    
    # ==================== 3. 采集成分股日K线数据 ====================
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def fetch_stock_daily(self, symbol: str, start_date: str = START_DATE, end_date: str = END_DATE) -> pd.DataFrame:
        """采集单只股票日K线数据"""
        try:
            df = ak.stock_zh_a_hist(symbol=symbol, period="daily",
                                    start_date=start_date, end_date=end_date, adjust="qfq")
            
            if df.empty:
                return df
            
            # 标准化列名 - AKShare返回12列
            df.columns = ['date', 'code', 'open', 'close', 'high', 'low', 'volume',
                         'amount', 'amplitude', 'pct_change', 'change', 'turnover']
            df['date'] = df['date'].astype(str).str.replace('-', '')
            df['symbol'] = symbol
            
            return df
        except Exception as e:
            print(f"    采集 {symbol} 失败: {e}")
            return pd.DataFrame()
    
    def save_stock_daily(self, df: pd.DataFrame):
        """保存成分股日K线数据"""
        if df.empty:
            return
        
        for _, row in df.iterrows():
            self.cursor.execute('''
                INSERT OR REPLACE INTO csi300_stock_daily 
                (symbol, code, date, open, high, low, close, volume, amount, 
                 amplitude, pct_change, change, turnover_rate)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (row['symbol'], row['code'], row['date'], row['open'], row['high'],
                  row['low'], row['close'], row['volume'], row['amount'],
                  row['amplitude'], row['pct_change'], row['change'], row['turnover']))
        
        self.conn.commit()
    
    def collect_all_constituent_daily(self, start_date: str = START_DATE, end_date: str = END_DATE):
        """采集所有成分股的日K线数据"""
        print(f"\n[3/4] 采集成分股日K线数据 ({start_date} - {end_date})...")
        
        symbols = self.get_constituent_symbols()
        if not symbols:
            print("  ⚠ 无成分股数据，请先执行步骤2")
            return
        
        print(f"  共 {len(symbols)} 只成分股需要采集")
        
        success_count = 0
        total_records = 0
        start_time = time.time()
        
        for i, symbol in enumerate(symbols, 1):
            try:
                # 检查已采集的最新日期
                self.cursor.execute(
                    'SELECT MAX(date) FROM csi300_stock_daily WHERE code = ?',
                    (symbol,)
                )
                last_date = self.cursor.fetchone()[0]
                
                if last_date and last_date >= end_date:
                    continue
                
                if last_date:
                    # 增量更新
                    actual_start = (datetime.strptime(last_date, '%Y%m%d') + timedelta(days=1)).strftime('%Y%m%d')
                else:
                    actual_start = start_date
                
                if actual_start > end_date:
                    continue
                
                # 采集数据
                df = self.fetch_stock_daily(symbol, actual_start, end_date)
                
                if not df.empty:
                    self.save_stock_daily(df)
                    success_count += 1
                    total_records += len(df)
                
                # 进度显示
                if i % 50 == 0 or i == len(symbols):
                    elapsed = time.time() - start_time
                    print(f"  [{i}/{len(symbols)}] 成功:{success_count} 记录:{total_records} 用时:{elapsed/60:.1f}分")
                
                time.sleep(0.05)  # 限速
                
            except Exception as e:
                if i % 50 == 0:
                    print(f"  [WARN] {symbol} 失败: {e}")
                time.sleep(0.1)
        
        elapsed = time.time() - start_time
        print(f"  ✓ 完成! 成功:{success_count} 只股票, 共 {total_records} 条记录, 用时:{elapsed/60:.1f}分")
    
    # ==================== 4. 采集每日涨跌停数据 ====================
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def fetch_limit_up_down(self, date: str) -> pd.DataFrame:
        """采集指定日期的涨跌停数据"""
        try:
            # 涨停数据
            up_df = ak.stock_zt_pool_em(date=date)
            if not up_df.empty:
                up_df['limit_type'] = 'up'
            
            # 跌停数据
            down_df = ak.stock_zt_pool_dtgc_em(date=date)
            if not down_df.empty:
                down_df['limit_type'] = 'down'
            
            # 合并数据
            if not up_df.empty and not down_df.empty:
                df = pd.concat([up_df, down_df], ignore_index=True)
            elif not up_df.empty:
                df = up_df
            elif not down_df.empty:
                df = down_df
            else:
                return pd.DataFrame()
            
            return df
        except Exception as e:
            return pd.DataFrame()
    
    def save_limit_up_down(self, df: pd.DataFrame, date: str):
        """保存涨跌停数据"""
        if df.empty:
            return
        
        for _, row in df.iterrows():
            try:
                self.cursor.execute('''
                    INSERT OR REPLACE INTO limit_up_down 
                    (date, code, name, close, pct_change, turnover_rate, limit_type, amount, industry)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (date, row.get('代码', ''), row.get('名称', ''),
                      row.get('最新价', 0), row.get('涨跌幅', 0),
                      row.get('换手率', 0), row.get('limit_type', ''),
                      row.get('成交额', 0), row.get('所属行业', '')))
            except:
                pass
        
        self.conn.commit()
    
    def collect_all_limit_data(self, start_date: str = START_DATE, end_date: str = END_DATE):
        """采集指定时间范围内的所有涨跌停数据"""
        print(f"\n[4/4] 采集涨跌停数据 ({start_date} - {end_date})...")
        
        # 生成交易日列表
        date_range = pd.date_range(start=start_date, end=end_date, freq='B')  # B = 工作日
        dates = [d.strftime('%Y%m%d') for d in date_range]
        
        print(f"  共 {len(dates)} 个交易日需要采集")
        
        success_count = 0
        total_records = 0
        start_time = time.time()
        
        for i, date in enumerate(dates, 1):
            try:
                # 检查是否已采集
                self.cursor.execute('SELECT COUNT(*) FROM limit_up_down WHERE date = ?', (date,))
                if self.cursor.fetchone()[0] > 0:
                    continue
                
                df = self.fetch_limit_up_down(date)
                
                if not df.empty:
                    self.save_limit_up_down(df, date)
                    success_count += 1
                    total_records += len(df)
                
                # 进度显示
                if i % 10 == 0 or i == len(dates):
                    elapsed = time.time() - start_time
                    print(f"  [{i}/{len(dates)}] 成功:{success_count} 记录:{total_records} 用时:{elapsed/60:.1f}分")
                
                time.sleep(0.2)  # 限速
                
            except Exception as e:
                if i % 10 == 0:
                    print(f"  [WARN] {date} 失败: {e}")
                time.sleep(0.3)
        
        elapsed = time.time() - start_time
        print(f"  ✓ 完成! 成功:{success_count} 天, 共 {total_records} 条记录, 用时:{elapsed/60:.1f}分")
    
    # ==================== 统计报告 ====================
    
    def print_stats(self):
        """打印数据统计"""
        print("\n" + "="*60)
        print("沪深300数据库统计报告")
        print("="*60)
        
        # 指数数据
        self.cursor.execute('SELECT COUNT(*), MIN(date), MAX(date) FROM csi300_index_daily')
        count, min_date, max_date = self.cursor.fetchone()
        print(f"\n[沪深300指数日K线]")
        print(f"  记录数: {count}")
        print(f"  时间范围: {min_date} - {max_date}")
        
        # 成分股列表
        self.cursor.execute('SELECT COUNT(*), MAX(date) FROM csi300_constituents')
        count, max_date = self.cursor.fetchone()
        print(f"\n[沪深300成分股]")
        print(f"  股票数: {count}")
        print(f"  最新权重日期: {max_date}")
        
        # 成分股日线
        self.cursor.execute('SELECT COUNT(*), COUNT(DISTINCT symbol), MIN(date), MAX(date) FROM csi300_stock_daily')
        count, stocks, min_date, max_date = self.cursor.fetchone()
        print(f"\n[成分股日K线]")
        print(f"  总记录数: {count}")
        print(f"  股票数: {stocks}")
        print(f"  时间范围: {min_date} - {max_date}")
        
        # 涨跌停数据
        self.cursor.execute('SELECT COUNT(*), COUNT(DISTINCT date) FROM limit_up_down')
        count, days = self.cursor.fetchone()
        print(f"\n[涨跌停数据]")
        print(f"  总记录数: {count}")
        print(f"  交易日数: {days}")
        
        print("\n" + "="*60)


# ==================== 主程序 ====================

def main():
    """主程序：按步骤执行数据采集"""
    collector = CSI300Collector()
    
    try:
        # 步骤1: 采集沪深300指数日K线
        df_index = collector.fetch_csi300_index_daily(START_DATE, END_DATE)
        collector.save_csi300_index_daily(df_index)
        
        # 步骤2: 采集成分股列表
        df_constituents = collector.fetch_csi300_constituents()
        collector.save_csi300_constituents(df_constituents)
        
        # 步骤3: 采集成分股日K线（耗时较长）
        collector.collect_all_constituent_daily(START_DATE, END_DATE)
        
        # 步骤4: 采集涨跌停数据
        collector.collect_all_limit_data(START_DATE, END_DATE)
        
        # 统计报告
        collector.print_stats()
        
        print("\n✓ 所有数据采集完成！")
        
    except KeyboardInterrupt:
        print("\n\n用户中断采集")
    except Exception as e:
        print(f"\n\n采集出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        collector.close()


if __name__ == "__main__":
    main()
