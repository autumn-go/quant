-- ============================================================
-- 量化平台 PostgreSQL 数据库初始化脚本
-- 数据库: quant_platform (主数据库)
-- 包含: 用户、策略、回测记录等
-- ============================================================

-- 创建扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- 1. 用户相关表
-- ============================================================

-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    display_name VARCHAR(100),
    avatar_url VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP WITH TIME ZONE
);

-- 用户API密钥表
CREATE TABLE IF NOT EXISTS user_api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key_name VARCHAR(100) NOT NULL,
    api_key_hash VARCHAR(255) NOT NULL,
    permissions JSONB DEFAULT '[]'::jsonb,
    is_active BOOLEAN DEFAULT TRUE,
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP WITH TIME ZONE
);

-- ============================================================
-- 2. 股票基础信息表 (从TimescaleDB同步的维度表)
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
-- 3. 策略表
-- ============================================================

CREATE TABLE IF NOT EXISTS strategies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    code TEXT NOT NULL,
    language VARCHAR(20) DEFAULT 'python' CHECK (language IN ('python', 'javascript', 'cpp')),
    parameters JSONB DEFAULT '{}'::jsonb,
    default_capital DECIMAL(20, 4) DEFAULT 1000000.00,
    default_benchmark VARCHAR(20) DEFAULT '000300.SH',
    is_public BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    version INTEGER DEFAULT 1,
    tags TEXT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_strategies_user_id ON strategies(user_id);
CREATE INDEX idx_strategies_is_public ON strategies(is_public) WHERE is_public = TRUE;

-- 策略版本历史表
CREATE TABLE IF NOT EXISTS strategy_versions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    strategy_id UUID NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    code TEXT NOT NULL,
    parameters JSONB DEFAULT '{}'::jsonb,
    change_log TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(strategy_id, version)
);

-- ============================================================
-- 4. 回测记录表
-- ============================================================

CREATE TABLE IF NOT EXISTS backtests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    strategy_id UUID NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100),
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    
    -- 回测时间范围
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    
    -- 回测参数
    initial_capital DECIMAL(20, 4) DEFAULT 1000000.00,
    benchmark VARCHAR(20) DEFAULT '000300.SH',
    frequency VARCHAR(10) DEFAULT 'daily' CHECK (frequency IN ('tick', 'minute', 'daily', 'weekly')),
    commission_rate DECIMAL(10, 6) DEFAULT 0.0003,
    slippage DECIMAL(10, 6) DEFAULT 0.0001,
    
    -- 结果指标 (回测完成后填充)
    total_return DECIMAL(10, 4),
    annualized_return DECIMAL(10, 4),
    benchmark_return DECIMAL(10, 4),
    alpha DECIMAL(10, 4),
    beta DECIMAL(10, 4),
    sharpe_ratio DECIMAL(10, 4),
    sortino_ratio DECIMAL(10, 4),
    max_drawdown DECIMAL(10, 4),
    max_drawdown_period INTEGER,
    volatility DECIMAL(10, 4),
    information_ratio DECIMAL(10, 4),
    calmar_ratio DECIMAL(10, 4),
    win_rate DECIMAL(10, 4),
    profit_loss_ratio DECIMAL(10, 4),
    
    -- 统计
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    
    -- 文件路径
    result_path VARCHAR(255),
    log_path VARCHAR(255),
    report_path VARCHAR(255),
    
    -- 错误信息
    error_message TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_backtests_strategy_id ON backtests(strategy_id);
CREATE INDEX idx_backtests_user_id ON backtests(user_id);
CREATE INDEX idx_backtests_status ON backtests(status);
CREATE INDEX idx_backtests_created_at ON backtests(created_at);

-- ============================================================
-- 5. 交易记录表
-- ============================================================

CREATE TABLE IF NOT EXISTS trades (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    backtest_id UUID NOT NULL REFERENCES backtests(id) ON DELETE CASCADE,
    
    -- 交易标的
    symbol VARCHAR(20) NOT NULL,
    market VARCHAR(10) NOT NULL,
    
    -- 交易信息
    side VARCHAR(10) NOT NULL CHECK (side IN ('buy', 'sell')),
    order_type VARCHAR(20) DEFAULT 'market' CHECK (order_type IN ('market', 'limit', 'stop')),
    
    -- 价格和数量
    quantity DECIMAL(20, 4) NOT NULL,
    price DECIMAL(20, 4) NOT NULL,
    amount DECIMAL(20, 4) NOT NULL,
    
    -- 费用
    commission DECIMAL(20, 4) DEFAULT 0,
    slippage DECIMAL(20, 4) DEFAULT 0,
    
    -- 时间
    trade_date DATE NOT NULL,
    trade_time TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- 信号信息
    signal_name VARCHAR(100),
    signal_params JSONB DEFAULT '{}'::jsonb,
    
    -- 持仓相关
    position_before DECIMAL(20, 4) DEFAULT 0,
    position_after DECIMAL(20, 4) DEFAULT 0,
    
    -- PnL (平仓时)
    realized_pnl DECIMAL(20, 4),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_trades_backtest_id ON trades(backtest_id);
CREATE INDEX idx_trades_symbol ON trades(symbol);
CREATE INDEX idx_trades_trade_date ON trades(trade_date);

-- ============================================================
-- 6. 持仓记录表 (每日快照)
-- ============================================================

CREATE TABLE IF NOT EXISTS positions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    backtest_id UUID NOT NULL REFERENCES backtests(id) ON DELETE CASCADE,
    symbol VARCHAR(20) NOT NULL,
    market VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    quantity DECIMAL(20, 4) DEFAULT 0,
    avg_cost DECIMAL(20, 4) DEFAULT 0,
    market_price DECIMAL(20, 4),
    market_value DECIMAL(20, 4),
    unrealized_pnl DECIMAL(20, 4),
    weight DECIMAL(10, 6),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(backtest_id, symbol, date)
);

CREATE INDEX idx_positions_backtest_id ON positions(backtest_id);
CREATE INDEX idx_positions_date ON positions(date);

-- ============================================================
-- 7. 账户净值历史表
-- ============================================================

CREATE TABLE IF NOT EXISTS equity_curve (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    backtest_id UUID NOT NULL REFERENCES backtests(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    total_equity DECIMAL(20, 4) NOT NULL,
    cash DECIMAL(20, 4) NOT NULL,
    market_value DECIMAL(20, 4) NOT NULL,
    daily_pnl DECIMAL(20, 4),
    daily_return DECIMAL(10, 6),
    benchmark_value DECIMAL(20, 4),
    benchmark_return DECIMAL(10, 6),
    drawdown DECIMAL(10, 6),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(backtest_id, date)
);

CREATE INDEX idx_equity_curve_backtest_id ON equity_curve(backtest_id);

-- ============================================================
-- 8. 系统配置表
-- ============================================================

CREATE TABLE IF NOT EXISTS system_configs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    config_key VARCHAR(100) UNIQUE NOT NULL,
    config_value TEXT,
    config_type VARCHAR(20) DEFAULT 'string' CHECK (config_type IN ('string', 'number', 'boolean', 'json')),
    description TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 9. 任务队列表 (用于 Celery 替代方案)
-- ============================================================

CREATE TABLE IF NOT EXISTS task_queue (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_type VARCHAR(50) NOT NULL,
    task_name VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    priority INTEGER DEFAULT 5,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'cancelled')),
    worker_id VARCHAR(100),
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    error_message TEXT,
    scheduled_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_task_queue_status ON task_queue(status, priority, scheduled_at);

-- ============================================================
-- 创建更新时间触发器函数
-- ============================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 为需要自动更新 updated_at 的表创建触发器
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_stocks_updated_at BEFORE UPDATE ON stocks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_strategies_updated_at BEFORE UPDATE ON strategies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- 插入默认数据
-- ============================================================

-- 默认系统配置
INSERT INTO system_configs (config_key, config_value, config_type, description) VALUES
    ('market.open_time', '09:30', 'string', 'A股开盘时间'),
    ('market.close_time', '15:00', 'string', 'A股收盘时间'),
    ('market.trading_days', '1,2,3,4,5', 'string', '交易日 (1=周一, 7=周日)'),
    ('backtest.default_capital', '1000000', 'number', '默认回测资金'),
    ('backtest.default_commission', '0.0003', 'number', '默认佣金率'),
    ('backtest.default_slippage', '0.0001', 'number', '默认滑点'),
    ('data.min_history_years', '5', 'number', '最小历史数据年限')
ON CONFLICT (config_key) DO NOTHING;

-- 默认管理员用户 (密码: admin123)
INSERT INTO users (username, email, password_hash, display_name, is_admin)
VALUES ('admin', 'admin@quant.com', crypt('admin123', gen_salt('bf')), '系统管理员', TRUE)
ON CONFLICT (username) DO NOTHING;