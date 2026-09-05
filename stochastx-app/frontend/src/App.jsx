import React, { useState, useEffect } from 'react';
import { 
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, AreaChart, Area 
} from 'recharts';
import { 
  Activity, TrendingUp, ShieldAlert, Cpu, Sliders, ArrowUpRight, ArrowDownRight, RefreshCw 
} from 'lucide-react';

export default function App() {
  const [tickers, setTickers] = useState([]);
  const [selectedTicker, setSelectedTicker] = useState('');
  const [deriskFactor, setDeriskFactor] = useState(0.40);
  const [feeBps, setFeeBps] = useState(5.0);
  const [calibrationWindow, setCalibrationWindow] = useState(252);
  
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch('http://localhost:8000/api/tickers')
      .then(res => res.json())
      .then(data => {
        if (data.tickers && data.tickers.length > 0) {
          setTickers(data.tickers);
          setSelectedTicker(data.tickers[0]);
        }
      })
      .catch(err => setError("Failed to connect to Quant Engine backend."));
  }, []);

  const runBacktest = () => {
    if (!selectedTicker) return;
    setLoading(true);
    setError(null);

    fetch('http://localhost:8000/api/backtest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ticker: selectedTicker,
        derisk_factor: parseFloat(deriskFactor),
        fee_bps: parseFloat(feeBps),
        calibration_window: parseInt(calibrationWindow)
      })
    })
      .then(res => {
        if (!res.ok) return res.json().then(err => { throw new Error(err.detail); });
        return res.json();
      })
      .then(data => {
        setResults(data);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  };

  useEffect(() => {
    if (selectedTicker) runBacktest();
  }, [selectedTicker]);

  // Format chart data for Recharts
  const chartData = results?.chart_data ? results.chart_data.dates.map((date, idx) => ({
    date,
    static_equity: results.chart_data.static_equity[idx],
    dynamic_equity: results.chart_data.dynamic_equity[idx],
    turbulent_prob: results.chart_data.turbulent_prob[idx],
    weight: results.chart_data.weights[idx]
  })) : [];

  const statCards = results ? [
    { label: "Strategy CAGR", value: `${results.dynamic_stats.cagr}%`, staticVal: `${results.static_stats.cagr}%`, icon: TrendingUp },
    { label: "Sharpe Ratio", value: results.dynamic_stats.sharpe, staticVal: results.static_stats.sharpe, icon: Activity },
    { label: "Max Drawdown", value: `${results.dynamic_stats.max_drawdown}%`, staticVal: `${results.static_stats.max_drawdown}%`, icon: ShieldAlert },
    { label: "Total Return", value: `${results.dynamic_stats.total_return}%`, staticVal: `${results.static_stats.total_return}%`, icon: Cpu },
  ] : [];

  return (
    <div className="flex h-screen bg-[#07090e] text-slate-100 font-sans overflow-hidden">
      
      {/* SIDEBAR NAVIGATION */}
      <aside className="w-64 bg-[#0b0f17] border-r border-slate-800 flex flex-col justify-between p-5">
        <div>
          <div className="flex items-center gap-3 mb-8">
            <div className="w-9 h-9 bg-emerald-500 rounded-xl flex items-center justify-center font-bold text-slate-950 shadow-lg shadow-emerald-500/20">
              SX
            </div>
            <div>
              <h1 className="font-bold tracking-wide text-sm text-white">STOCHASTX</h1>
              <p className="text-xs text-slate-400">Quant Engine v2.0</p>
            </div>
          </div>

          <nav className="space-y-1 text-sm">
            <a href="#" className="flex items-center gap-3 px-3 py-2.5 rounded-lg bg-emerald-500/10 text-emerald-400 font-medium">
              <Activity size={18} /> Regime Dashboard
            </a>
            <a href="#" className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800/50 transition">
              <TrendingUp size={18} /> Asset Universe
            </a>
            <a href="#" className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800/50 transition">
              <Sliders size={18} /> Model Parameters
            </a>
          </nav>
        </div>

        <div className="bg-[#111622] border border-slate-800/80 rounded-xl p-3 text-xs text-slate-400">
          <p className="font-semibold text-slate-200 mb-1">Engine Status</p>
          <div className="flex items-center gap-2 text-emerald-400">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span> GMM Active (2 Regimes)
          </div>
        </div>
      </aside>

      {/* MAIN CONTENT AREA */}
      <main className="flex-1 flex flex-col overflow-y-auto">
        
        {/* TOPBAR */}
        <header className="h-16 border-b border-slate-800 bg-[#0b0f17]/80 backdrop-blur-md px-6 flex items-center justify-between sticky top-0 z-20">
          <div className="flex items-center gap-4">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Target Asset:</span>
            <select 
              value={selectedTicker} 
              onChange={(e) => setSelectedTicker(e.target.value)}
              className="bg-[#121824] border border-slate-700 text-slate-200 text-sm rounded-lg px-3 py-1.5 focus:outline-none focus:border-emerald-500"
            >
              {tickers.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>

          <div className="flex items-center gap-3">
            <button 
              onClick={runBacktest}
              disabled={loading}
              className="flex items-center gap-2 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-semibold px-4 py-1.5 rounded-lg text-sm transition shadow-lg shadow-emerald-500/10 disabled:opacity-50"
            >
              <RefreshCw size={15} className={loading ? "animate-spin" : ""} /> 
              {loading ? "Simulating..." : "Run Simulation"}
            </button>
          </div>
        </header>

        {/* DASHBOARD BODY */}
        <div className="p-6 space-y-6 max-w-7xl w-full mx-auto">
          
          {error && (
            <div className="bg-rose-500/10 border border-rose-500/20 text-rose-400 p-4 rounded-xl text-sm">
              {error}
            </div>
          )}

          {/* PARAMETER CONTROL PANEL */}
          <div className="bg-[#111622] border border-slate-800/80 rounded-2xl p-5 grid grid-cols-3 gap-6">
            <div>
              <label className="block text-xs text-slate-400 mb-1.5 font-medium">De-Risk Factor ({deriskFactor})</label>
              <input 
                type="range" min="0" max="1" step="0.05" value={deriskFactor} 
                onChange={(e) => setDeriskFactor(e.target.value)}
                className="w-full accent-emerald-500 bg-slate-800 rounded-lg cursor-pointer"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1.5 font-medium">Transaction Fees ({feeBps} bps)</label>
              <input 
                type="range" min="0" max="20" step="1" value={feeBps} 
                onChange={(e) => setFeeBps(e.target.value)}
                className="w-full accent-emerald-500 bg-slate-800 rounded-lg cursor-pointer"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1.5 font-medium">Calibration Window ({calibrationWindow} Days)</label>
              <input 
                type="number" value={calibrationWindow} 
                onChange={(e) => setCalibrationWindow(e.target.value)}
                className="w-full bg-[#0b0f17] border border-slate-700 text-slate-200 text-sm rounded-lg px-3 py-1 focus:outline-none focus:border-emerald-500"
              />
            </div>
          </div>

          {/* STATS GRID */}
          <div className="grid grid-cols-4 gap-4">
            {statCards.map((stat, idx) => {
              const Icon = stat.icon;
              return (
                <div key={idx} className="bg-[#111622] border border-slate-800/80 rounded-2xl p-5 relative overflow-hidden">
                  <div className="flex items-center justify-between text-slate-400 mb-3">
                    <span className="text-xs font-medium">{stat.label}</span>
                    <Icon size={18} className="text-emerald-400" />
                  </div>
                  <div className="flex items-baseline justify-between">
                    <span className="text-2xl font-bold tracking-tight text-white">{stat.value}</span>
                    <span className="text-xs text-slate-500 font-medium">Static: {stat.staticVal}</span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* MAIN EQUITY CURVE CHART */}
          <div className="bg-[#111622] border border-slate-800/80 rounded-2xl p-6">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-base font-bold text-white">Equity Curve Performance</h2>
                <p className="text-xs text-slate-400">Dynamic GMM Regime Hedging vs. Buy & Hold Static Equity ($100k Base)</p>
              </div>
              <div className="flex items-center gap-4 text-xs font-medium">
                <span className="flex items-center gap-1.5 text-emerald-400"><span className="w-3 h-1 bg-emerald-500 rounded"></span> Dynamic Strategy</span>
                <span className="flex items-center gap-1.5 text-slate-400"><span className="w-3 h-1 bg-slate-500 rounded"></span> Static Asset</span>
              </div>
            </div>

            <div className="h-[360px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <XAxis dataKey="date" stroke="#475569" fontSize={11} tickLine={false} />
                  <YAxis stroke="#475569" fontSize={11} tickLine={false} domain={['auto', 'auto']} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#0b0f17', borderColor: '#1e293b', borderRadius: '12px', fontSize: '12px' }}
                    itemStyle={{ color: '#f8fafc' }}
                  />
                  <Line type="monotone" dataKey="dynamic_equity" stroke="#10b981" strokeWidth={2} dot={false} name="Dynamic Equity" />
                  <Line type="monotone" dataKey="static_equity" stroke="#64748b" strokeWidth={1.5} dot={false} strokeDasharray="3 3" name="Static Equity" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* SECONDARY REGIME SUBPLOT */}
          <div className="bg-[#111622] border border-slate-800/80 rounded-2xl p-6">
            <div className="mb-4">
              <h2 className="text-sm font-bold text-white">Market Turbulence Probability & Asset Weight Allocation</h2>
              <p className="text-xs text-slate-400">Real-time GMM regime classification confidence scores</p>
            </div>

            <div className="h-[180px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData}>
                  <XAxis dataKey="date" stroke="#475569" fontSize={11} tickLine={false} />
                  <YAxis stroke="#475569" fontSize={11} tickLine={false} domain={[0, 1]} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#0b0f17', borderColor: '#1e293b', borderRadius: '12px', fontSize: '12px' }}
                  />
                  <Area type="monotone" dataKey="turbulent_prob" stroke="#f43f5e" fill="#f43f5e" fillOpacity={0.15} strokeWidth={1.5} name="Turbulent Prob" />
                  <Area type="monotone" dataKey="weight" stroke="#38bdf8" fill="#38bdf8" fillOpacity={0.1} strokeWidth={1.5} name="Allocation Weight" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

        </div>
      </main>
    </div>
  );
}