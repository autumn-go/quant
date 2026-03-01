// API 配置
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

// 通用请求函数
async function fetchAPI(endpoint: string, options?: RequestInit) {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });
  
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }
  
  return response.json();
}

// 股票相关 API
export const stockAPI = {
  // 获取股票列表
  getStocks: (market?: string, limit: number = 100) => 
    fetchAPI(`/stocks?${market ? `market=${market}&` : ''}limit=${limit}`),
  
  // 获取股票历史价格
  getPrices: (symbol: string, days: number = 30) =>
    fetchAPI(`/stocks/${symbol}/prices?days=${days}`),
};

// 市场数据 API
export const marketAPI = {
  // 获取指数数据
  getIndices: () => fetchAPI('/market/indices'),
  
  // 获取板块数据
  getSectors: () => fetchAPI('/sectors'),
};

// 策略相关 API
export const strategyAPI = {
  // 获取策略统计
  getStats: () => fetchAPI('/strategies/stats'),
  
  // 获取最新信号
  getRecentSignals: () => fetchAPI('/signals/recent'),
};

// 回测 API
export const backtestAPI = {
  // 执行回测
  runBacktest: (data: {
    strategy_code: string;
    strategy_params: Record<string, any>;
    symbol?: string;
    start_date?: string;
    end_date?: string;
    initial_capital?: number;
    commission?: number;
  }) => fetchAPI('/backtest/run', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
};

export default {
  stock: stockAPI,
  market: marketAPI,
  strategy: strategyAPI,
  backtest: backtestAPI,
};