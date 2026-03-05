// 策略代码编辑器
import React, { useState } from 'react';
import Editor from '@monaco-editor/react';
import { Play, Save, FileCode, Settings, ChevronDown, ChevronRight } from 'lucide-react';
import { backtestAPI } from '../api';
import './StrategyEditor.css';

// 默认策略模板
const DEFAULT_STRATEGY = `class DualMAStrategy(bt.Strategy):
    \"\"\"
    双均线策略 - 金叉买入，死叉卖出
    
    参数:
        fast: 快线周期
        slow: 慢线周期
    \"\"\"
    params = (
        ('fast', 10),
        ('slow', 30),
    )
    
    def __init__(self):
        # 初始化指标
        self.fast_ma = bt.ind.SMA(period=self.p.fast)
        self.slow_ma = bt.ind.SMA(period=self.p.slow)
        self.crossover = bt.ind.CrossOver(self.fast_ma, self.slow_ma)
        
        # 记录交易
        self.trades = []
        
    def next(self):
        # 当前没有持仓
        if not self.position:
            # 金叉买入
            if self.crossover > 0:
                self.buy()
                self.trades.append({
                    'date': self.data.datetime.date(0),
                    'action': 'BUY',
                    'price': self.data.close[0]
                })
        # 当前有持仓
        else:
            # 死叉卖出
            if self.crossover < 0:
                self.sell()
                self.trades.append({
                    'date': self.data.datetime.date(0),
                    'action': 'SELL',
                    'price': self.data.close[0]
                })
    
    def stop(self):
        # 回测结束时的处理
        print(f'回测完成！总交易次数: {len(self.trades)}')
`;

// 策略模板列表
const STRATEGY_TEMPLATES = [
  { name: '双均线策略', code: 'dual_ma', desc: '金叉买入，死叉卖出' },
  { name: 'MACD策略', code: 'macd', desc: 'MACD金叉死叉' },
  { name: 'RSI策略', code: 'rsi', desc: '超买超卖' },
  { name: '布林带策略', code: 'bollinger', desc: '突破上轨买入' },
  { name: '动量策略', code: 'momentum', desc: '价格动量跟踪' },
];

interface StrategyEditorProps {
  initialCode?: string;
  onSave?: (code: string, params: Record<string, any>) => void;
}

const StrategyEditor: React.FC<StrategyEditorProps> = ({
  initialCode = DEFAULT_STRATEGY,
  onSave,
}) => {
  const [code, setCode] = useState(initialCode);
  const [strategyName, setStrategyName] = useState('双均线策略');
  const [showTemplates, setShowTemplates] = useState(false);
  const [params, setParams] = useState({
    fast: 10,
    slow: 30,
    initial_capital: 1000000,
    commission: 0.0003,
  });
  const [isRunning, setIsRunning] = useState(false);
  const [consoleOutput, setConsoleOutput] = useState<string[]>([]);

  const handleEditorChange = (value: string | undefined) => {
    if (value !== undefined) {
      setCode(value);
    }
  };

  const handleSave = () => {
    onSave?.(code, params);
    addConsoleLog('策略已保存');
  };

  const handleRun = async () => {
    setIsRunning(true);
    addConsoleLog('开始回测...');
    
    try {
      const result = await backtestAPI.runBacktest({
        strategy_code: code,
        strategy_params: {
          fast: params.fast,
          slow: params.slow,
        },
        symbol: '600000.SH', // 默认测试浦发银行
        start_date: '2024-01-01',
        end_date: '2024-12-31',
        initial_capital: params.initial_capital,
        commission: params.commission,
      });
      
      if (result.success) {
        addConsoleLog(`回测完成！`);
        addConsoleLog(`最终资金: ¥${result.final_value.toLocaleString()}`);
        addConsoleLog(`总收益率: ${result.total_return}%`);
        addConsoleLog(`年化收益: ${result.annual_return}%`);
        addConsoleLog(`最大回撤: ${result.max_drawdown}%`);
        addConsoleLog(`夏普比率: ${result.sharpe_ratio}`);
        addConsoleLog(`交易次数: ${result.total_trades} (胜: ${result.winning_trades} / 负: ${result.losing_trades})`);
      } else {
        addConsoleLog(`回测失败: ${result.error}`);
      }
    } catch (error) {
      addConsoleLog(`错误: ${error}`);
    } finally {
      setIsRunning(false);
    }
  };

  const addConsoleLog = (message: string) => {
    const timestamp = new Date().toLocaleTimeString();
    setConsoleOutput(prev => [...prev, `[${timestamp}] ${message}`]);
  };

  const loadTemplate = (templateCode: string) => {
    const templates: Record<string, string> = {
      dual_ma: DEFAULT_STRATEGY,
      macd: `class MacdStrategy(bt.Strategy):
    params = (('fast', 12), ('slow', 26), ('signal', 9))
    
    def __init__(self):
        self.macd = bt.ind.MACD(
            period1=self.p.fast,
            period2=self.p.slow,
            period_signal=self.p.signal
        )
    
    def next(self):
        if not self.position:
            if self.macd.macd > self.macd.signal:
                self.buy()
        elif self.macd.macd < self.macd.signal:
            self.sell()`,
      rsi: `class RsiStrategy(bt.Strategy):
    params = (('period', 14), ('overbought', 70), ('oversold', 30))
    
    def __init__(self):
        self.rsi = bt.ind.RSI(period=self.p.period)
    
    def next(self):
        if not self.position:
            if self.rsi < self.p.oversold:
                self.buy()
        elif self.rsi > self.p.overbought:
            self.sell()`,
      bollinger: `class BollingerStrategy(bt.Strategy):
    params = (('period', 20), ('devfactor', 2))
    
    def __init__(self):
        self.boll = bt.ind.BollingerBands(
            period=self.p.period,
            devfactor=self.p.devfactor
        )
    
    def next(self):
        if not self.position:
            if self.data.close > self.boll.lines.top:
                self.buy()
        elif self.data.close < self.boll.lines.mid:
            self.sell()`,
      momentum: `class MomentumStrategy(bt.Strategy):
    params = (('period', 20),)
    
    def __init__(self):
        self.momentum = bt.ind.Momentum(period=self.p.period)
    
    def next(self):
        if not self.position:
            if self.momentum > 0:
                self.buy()
        elif self.momentum < 0:
            self.sell()`,
    };
    
    setCode(templates[templateCode] || DEFAULT_STRATEGY);
    setShowTemplates(false);
    addConsoleLog(`已加载模板: ${templateCode}`);
  };

  return (
    <div className="strategy-editor">
      {/* 工具栏 */}
      <div className="editor-toolbar">
        <div className="toolbar-left">
          <div className="strategy-selector">
            <FileCode size={18} />
            <input
              type="text"
              value={strategyName}
              onChange={(e) => setStrategyName(e.target.value)}
              className="strategy-name-input"
              placeholder="策略名称"
            />
          </div>
          
          <div className="template-dropdown">
            <button 
              className="btn btn-outline btn-sm"
              onClick={() => setShowTemplates(!showTemplates)}
            >
              模板
              {showTemplates ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            </button>
            
            {showTemplates && (
              <div className="template-menu">
                {STRATEGY_TEMPLATES.map((t) => (
                  <div
                    key={t.code}
                    className="template-item"
                    onClick={() => loadTemplate(t.code)}
                  >
                    <div className="template-item-name">{t.name}</div>
                    <div className="template-item-desc">{t.desc}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
        
        <div className="toolbar-right">
          <button className="btn btn-outline" onClick={handleSave}>
            <Save size={16} />
            保存
          </button>
          <button 
            className="btn btn-primary" 
            onClick={handleRun}
            disabled={isRunning}
          >
            <Play size={16} />
            {isRunning ? '运行中...' : '运行回测'}
          </button>
        </div>
      </div>

      <div className="editor-main">
        {/* 代码编辑区 */}
        <div className="code-section">
          <Editor
            height="100%"
            defaultLanguage="python"
            value={code}
            onChange={handleEditorChange}
            theme="vs-dark"
            options={{
              minimap: { enabled: false },
              fontSize: 14,
              lineNumbers: 'on',
              roundedSelection: false,
              scrollBeyondLastLine: false,
              readOnly: false,
              automaticLayout: true,
              padding: { top: 16 },
            }}
          />
        </div>

        {/* 右侧参数面板 */}
        <div className="params-section">
          <div className="params-header">
            <Settings size={16} />
            <span>参数设置</span>
          </div>
          
          <div className="params-content">
            <div className="param-group">
              <label>快线周期 (fast)</label>
              <input
                type="number"
                value={params.fast}
                onChange={(e) => setParams({ ...params, fast: parseInt(e.target.value) })}
              />
            </div>
            
            <div className="param-group">
              <label>慢线周期 (slow)</label>
              <input
                type="number"
                value={params.slow}
                onChange={(e) => setParams({ ...params, slow: parseInt(e.target.value) })}
              />
            </div>
            
            <div className="param-group">
              <label>初始资金</label>
              <input
                type="number"
                value={params.initial_capital}
                onChange={(e) => setParams({ ...params, initial_capital: parseInt(e.target.value) })}
              />
            </div>
            
            <div className="param-group">
              <label>佣金率</label>
              <input
                type="number"
                step="0.0001"
                value={params.commission}
                onChange={(e) => setParams({ ...params, commission: parseFloat(e.target.value) })}
              />
            </div>
          </div>
          
          {/* 控制台输出 */}
          <div className="console-section">
            <div className="console-header">控制台</div>
            <div className="console-content">
              {consoleOutput.map((log, idx) => (
                <div key={idx} className="console-line">{log}</div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default StrategyEditor;
