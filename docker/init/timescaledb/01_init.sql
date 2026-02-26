-- ============================================================
-- 量化平台 TimescaleDB 数据库初始化脚本
-- 数据库: quant_market (时序数据库)
-- 包含: 股票行情数据
-- ============================================================

-- 创建扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ============================================================
-- 1. 股票基础信息表 (与PostgreSQL同步)
-- ============================================================

CREATE TABLE IF NOT EXISTS stocks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) NOT NULL,
    name VARCHAR(100) NOT NULL,
    market VARCHAR(10) NOT NULL CHECK (market IN ('SH', 'SZ', 'HK', 'US')),
    exchange VARCHAR(20),
    industry VARCHAR(100),
    sector VARCHAR(100),
    listing_date DATE,
    delisted BOOLEAN DEFAULT FALSE,
    currency VARCHAR(10) DEFAULT 'CNY',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, market)
);

CREATE INDEX idx_stocks_symbol ON stocks(symbol);
CREATE INDEX idx_stocks_market ON stocks(market);
CREATE INDEX idx_stocks_industry ON stocks(industry);

-- ============================================================
-- 2. 日线行情数据表 ( hypertable )
-- ============================================================

CREATE TABLE IF NOT EXISTS daily_prices (
    id UUID DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) NOT NULL,
    market VARCHAR(10) NOT NULL,
    trade_date DATE NOT NULL,
    
    -- 基础价格
    open DECIMAL(20, 4) NOT NULL,
    high DECIMAL(20, 4) NOT NULL,
    low DECIMAL(20, 4) NOT NULL,
    close DECIMAL(20, 4) NOT NULL,
    
    -- 成交量和成交额
    volume BIGINT NOT NULL,
    amount DECIMAL(20, 4),
    
    -- 复权因子
    adj_factor DECIMAL(20, 8) DEFAULT 1.0,
    
    -- 前复权价格
    open_adj DECIMAL(20, 4),
    high_adj DECIMAL(20, 4),
    low_adj DECIMAL(20, 4),
    close_adj DECIMAL(20, 4),
    
    -- 涨跌幅
    change_pct DECIMAL(10, 6),
    
    -- 市值
    market_cap DECIMAL(20, 4),
    circulating_cap DECIMAL(20, 4),
    
    -- 换手率
    turnover_rate DECIMAL(10, 6),
    
    -- 数据源
    source VARCHAR(50),
    
    -- 元数据
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (symbol, market, trade_date)
);

-- 转换为 hypertable (按日期分区，1年一个chunk)
SELECT create_hypertable('daily_prices', 'trade_date', 
    chunk_time_interval => INTERVAL '1 year',
    if_not_exists => TRUE);

-- 创建索引
CREATE INDEX idx_daily_prices_symbol_date ON daily_prices(symbol, market, trade_date DESC);
CREATE INDEX idx_daily_prices_date ON daily_prices(trade_date DESC);

-- ============================================================
-- 3. 分钟线行情数据表 ( hypertable )
-- ============================================================

CREATE TABLE IF NOT EXISTS minute_prices (
    id UUID DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) NOT NULL,
    market VARCHAR(10) NOT NULL,
    trade_time TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- 基础价格
    open DECIMAL(20, 4) NOT NULL,
    high DECIMAL(20, 4) NOT NULL,
    low DECIMAL(20, 4) NOT NULL,
    close DECIMAL(20, 4) NOT NULL,
    
    -- 成交量和成交额
    volume BIGINT NOT NULL,
    amount DECIMAL(20, 4),
    
    -- 复权因子
    adj_factor DECIMAL(20, 8) DEFAULT 1.0,
    
    -- 周期类型 (1min, 5min, 15min, 30min, 60min)
    period VARCHAR(10) DEFAULT '1min' CHECK (period IN ('1min', '5min', '15min', '30min', '60min')),
    
    -- 数据源
    source VARCHAR(50),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (symbol, market, trade_time, period)
);

-- 转换为 hypertable (按时间分区，7天一个chunk)
SELECT create_hypertable('minute_prices', 'trade_time', 
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE);

-- 创建索引
CREATE INDEX idx_minute_prices_symbol_time ON minute_prices(symbol, market, trade_time DESC);
CREATE INDEX idx_minute_prices_time ON minute_prices(trade_time DESC);

-- ============================================================
-- 4. Tick数据表 ( hypertable ) - 可选，用于高频策略
-- ============================================================

CREATE TABLE IF NOT EXISTS tick_data (
    id UUID DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) NOT NULL,
    market VARCHAR(10) NOT NULL,
    trade_time TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- 价格
    price DECIMAL(20, 4) NOT NULL,
    volume BIGINT NOT NULL,
    amount DECIMAL(20, 4),
    
    -- 买卖盘
    bid1_price DECIMAL(20, 4),
    bid1_volume BIGINT,
    ask1_price DECIMAL(20, 4),
    ask1_volume BIGINT,
    
    -- 成交类型
    trade_type VARCHAR(10), -- buy/sell/unknown
    
    -- 数据源
    source VARCHAR(50),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (symbol, market, trade_time, id)
);

-- 转换为 hypertable (按时间分区，1天一个chunk)
SELECT create_hypertable('tick_data', 'trade_time', 
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

-- 创建索引
CREATE INDEX idx_tick_data_symbol_time ON tick_data(symbol, market, trade_time DESC);
CREATE INDEX idx_tick_data_time ON tick_data(trade_time DESC);

-- ============================================================
-- 5. 复权因子历史表
-- ============================================================

CREATE TABLE IF NOT EXISTS adjustment_factors (
    id UUID DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) NOT NULL,
    market VARCHAR(10) NOT NULL,
    ex_date DATE NOT NULL,
    
    -- 复权类型
    adj_type VARCHAR(20) NOT NULL CHECK (adj_type IN ('split', 'dividend', 'bonus', 'rights')),
    
    -- 复权因子
    factor DECIMAL(20, 8) NOT NULL,
    
    -- 详细信息
    description TEXT,
    
    -- 送股、配股、分红详情
    bonus_ratio DECIMAL(10, 6), -- 送股比例
    rights_ratio DECIMAL(10, 6), -- 配股比例
    rights_price DECIMAL(20, 4), -- 配股价
    dividend DECIMAL(20, 4), -- 每股分红
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (symbol, market, ex_date, adj_type)
);

-- 转换为 hypertable
SELECT create_hypertable('adjustment_factors', 'ex_date', 
    chunk_time_interval => INTERVAL '1 year',
    if_not_exists => TRUE);

CREATE INDEX idx_adjustment_factors_symbol ON adjustment_factors(symbol, market);

-- ============================================================
-- 6. 财务数据表
-- ============================================================

CREATE TABLE IF NOT EXISTS financial_data (
    id UUID DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) NOT NULL,
    market VARCHAR(10) NOT NULL,
    report_date DATE NOT NULL,
    report_type VARCHAR(10) NOT NULL CHECK (report_type IN ('Q1', 'Q2', 'Q3', 'Annual')),
    
    -- 主要财务指标
    eps DECIMAL(20, 4), -- 每股收益
    bps DECIMAL(20, 4), -- 每股净资产
    roe DECIMAL(10, 6), -- 净资产收益率
    roa DECIMAL(10, 6), -- 总资产收益率
    
    -- 盈利能力
    gross_profit_margin DECIMAL(10, 6),
    net_profit_margin DECIMAL(10, 6),
    
    -- 估值指标
    pe_ratio DECIMAL(10, 4),
    pb_ratio DECIMAL(10, 4),
    ps_ratio DECIMAL(10, 4),
    
    -- 成长性
    revenue_growth DECIMAL(10, 6),
    profit_growth DECIMAL(10, 6),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (symbol, market, report_date, report_type)
);

-- 转换为 hypertable
SELECT create_hypertable('financial_data', 'report_date', 
    chunk_time_interval => INTERVAL '1 year',
    if_not_exists => TRUE);

CREATE INDEX idx_financial_data_symbol ON financial_data(symbol, market);

-- ============================================================
-- 7. 指数成分股表
-- ============================================================

CREATE TABLE IF NOT EXISTS index_components (
    id UUID DEFAULT uuid_generate_v4(),
    index_symbol VARCHAR(20) NOT NULL, -- 如 000300.SH
    component_symbol VARCHAR(20) NOT NULL,
    component_market VARCHAR(10) NOT NULL,
    effective_date DATE NOT NULL,
    weight DECIMAL(10, 6), -- 权重
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (index_symbol, component_symbol, effective_date)
);

-- 转换为 hypertable
SELECT create_hypertable('index_components', 'effective_date', 
    chunk_time_interval => INTERVAL '1 year',
    if_not_exists => TRUE);

CREATE INDEX idx_index_components_symbol ON index_components(index_symbol);

-- ============================================================
-- 8. 数据源状态表
-- ============================================================

CREATE TABLE IF NOT EXISTS data_source_status (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_name VARCHAR(50) NOT NULL UNIQUE,
    source_type VARCHAR(20) NOT NULL, -- akshare, tushare, yfinance, etc.
    last_sync_time TIMESTAMP WITH TIME ZONE,
    last_sync_status VARCHAR(20) DEFAULT 'pending',
    last_error_message TEXT,
    sync_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    config JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 9. 创建连续聚合视图 (日线数据的周/月线)
-- ============================================================

-- 周线数据视图
CREATE MATERIALIZED VIEW IF NOT EXISTS weekly_prices
WITH (timescaledb.continuous) AS
SELECT
    symbol,
    market,
    time_bucket('1 week', trade_date) AS week,
    first(open, trade_date) AS open,
    max(high) AS high,
    min(low) AS low,
    last(close, trade_date) AS close,
    sum(volume) AS volume,
    sum(amount) AS amount,
    last(adj_factor, trade_date) AS adj_factor
FROM daily_prices
GROUP BY symbol, market, time_bucket('1 week', trade_date)
WITH NO DATA;

-- 月线数据视图
CREATE MATERIALIZED VIEW IF NOT EXISTS monthly_prices
WITH (timescaledb.continuous) AS
SELECT
    symbol,
    market,
    time_bucket('1 month', trade_date) AS month,
    first(open, trade_date) AS open,
    max(high) AS high,
    min(low) AS low,
    last(close, trade_date) AS close,
    sum(volume) AS volume,
    sum(amount) AS amount,
    last(adj_factor, trade_date) AS adj_factor
FROM daily_prices
GROUP BY symbol, market, time_bucket('1 month', trade_date)
WITH NO DATA;

-- ============================================================
-- 10. 创建更新触发器
-- ============================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_stocks_updated_at BEFORE UPDATE ON stocks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_data_source_status_updated_at BEFORE UPDATE ON data_source_status
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- 11. 插入示例股票数据 (A股主要指数)
-- ============================================================

INSERT INTO stocks (symbol, name, market, exchange, industry, listing_date) VALUES
    ('000001', '上证指数', 'SH', 'SSE', 'Index', '1991-07-15'),
    ('000300', '沪深300', 'SH', 'SSE', 'Index', '2005-04-08'),
    ('000905', '中证500', 'SH', 'SSE', 'Index', '2007-01-15'),
    ('000016', '上证50', 'SH', 'SSE', 'Index', '2004-01-02'),
    ('399001', '深证成指', 'SZ', 'SZSE', 'Index', '1995-01-23'),
    ('399006', '创业板指', 'SZ', 'SZSE', 'Index', '2010-06-01'),
    ('HSI', '恒生指数', 'HK', 'HKEX', 'Index', '1969-11-24')
ON CONFLICT (symbol, market) DO NOTHING;

-- 插入数据源配置
INSERT INTO data_source_status (source_name, source_type, config) VALUES
    ('akshare_daily', 'akshare', '{"type": "daily", "market": "A"}'),
    ('akshare_minute', 'akshare', '{"type": "minute", "market": "A"}'),
    ('tushare_pro', 'tushare', '{"type": "daily", "market": "A"}'),
    ('yfinance_hk', 'yfinance', '{"type": "daily", "market": "HK"}')
ON CONFLICT (source_name) DO NOTHING;