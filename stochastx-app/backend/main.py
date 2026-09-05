import sys
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import numpy as np
import pandas as pd
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import RobustScaler

# 1. Resolve root folder (StochastX/) relative to this file
ROOT_DIR = Path(__file__).resolve().parent.parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

DATA_PATH = ROOT_DIR / "nse_5yr_data.csv"
DATA_CACHE = {}

# Lifespan context manager replacing deprecated @app.on_event
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        df = pd.read_csv(DATA_PATH, index_col=0, parse_dates=True)
        DATA_CACHE["prices"] = df
        print(f"Successfully loaded dataset from {DATA_PATH} with {len(df)} rows.")
    except Exception as e:
        print(f"Critical error loading dataset at {DATA_PATH}: {e}")
    yield
    DATA_CACHE.clear()

app = FastAPI(title="StochastX Quant Engine", version="2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class BacktestRequest(BaseModel):
    ticker: str
    derisk_factor: float = 0.40
    fee_bps: float = 5.0
    calibration_window: int = 252

@app.get("/")
def root_health_check():
    return {"status": "online", "service": "StochastX Quant Engine v2.0"}

@app.get("/api/tickers")
def get_tickers():
    if "prices" not in DATA_CACHE:
        raise HTTPException(status_code=500, detail="Dataset not loaded into memory.")
    return {"tickers": list(DATA_CACHE["prices"].columns)}

@app.post("/api/backtest")
def run_backtest_endpoint(req: BacktestRequest):
    df = DATA_CACHE.get("prices")
    if df is None or req.ticker not in df.columns:
        raise HTTPException(status_code=400, detail=f"Ticker '{req.ticker}' not found.")

    prices = df[req.ticker].dropna()
    log_returns = np.log(prices / prices.shift(1))
    rolling_vol = log_returns.ewm(span=15).std() * np.sqrt(252)
    features = pd.DataFrame({'return': log_returns, 'volatility': rolling_vol}).dropna()

    if len(features) <= req.calibration_window:
        raise HTTPException(status_code=400, detail=f"Insufficient data rows ({len(features)}) for window size {req.calibration_window}.")

    scaler = RobustScaler()
    scaler.fit(features.iloc[:req.calibration_window])
    scaled_features = pd.DataFrame(scaler.transform(features), index=features.index, columns=features.columns)

    gmm = GaussianMixture(n_components=2, covariance_type='full', n_init=10, random_state=42)
    try:
        gmm.fit(scaled_features.iloc[:req.calibration_window])
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Regime engine convergence error: {str(e)}")

    vol_idx = scaled_features.columns.get_loc('volatility')
    high_vol_cluster = 1 if gmm.means_[1][vol_idx] > gmm.means_[0][vol_idx] else 0

    probs = gmm.predict_proba(scaled_features)
    raw_turb_prob = pd.Series(probs[:, high_vol_cluster], index=scaled_features.index)
    features['Turbulent_Prob'] = raw_turb_prob.ewm(span=5).mean()
    features['Execution_Prob'] = features['Turbulent_Prob'].shift(1).fillna(0)

    df_bt = features.copy()
    weights = 1.0 - (df_bt['Execution_Prob'] * (1.0 - req.derisk_factor))
    simple_asset_returns = np.exp(df_bt['return']) - 1.0
    daily_rf = 0.065 / 252.0
    fee_ratio = req.fee_bps / 10000.0
    transaction_costs = weights.diff().abs().fillna(0) * fee_ratio
    
    df_bt['Strategy_Return'] = (weights * simple_asset_returns) + ((1.0 - weights) * daily_rf) - transaction_costs
    
    initial_capital = 100000.0
    df_bt['Static_Equity'] = initial_capital * (1.0 + simple_asset_returns).cumprod()
    df_bt['Dynamic_Equity'] = initial_capital * (1.0 + df_bt['Strategy_Return']).cumprod()

    # Clean out any float edge-cases (inf/nan) before sending JSON
    df_bt = df_bt.replace([np.inf, -np.inf], np.nan).fillna(0)

    n_years = max(len(df_bt) / 252.0, 0.001)

    def compute_stats(rets, eq):
        tr = ((eq.iloc[-1] - initial_capital) / initial_capital) * 100.0
        cagr = ((max(eq.iloc[-1], 1e-6) / initial_capital) ** (1.0 / n_years) - 1.0) * 100.0
        mean_ret = rets.mean() * 252.0
        vol_ret = rets.std() * np.sqrt(252)
        sharpe = (mean_ret - 0.065) / vol_ret if vol_ret > 0 else 0.0
        max_dd = ((eq - eq.cummax()) / eq.cummax()).min() * 100.0
        return {
            "total_return": round(float(tr), 2),
            "cagr": round(float(cagr), 2),
            "sharpe": round(float(sharpe), 2),
            "max_drawdown": round(float(max_dd), 2)
        }

    chart_data = {
        "dates": df_bt.index.strftime('%Y-%m-%d').tolist(),
        "static_equity": df_bt['Static_Equity'].round(2).tolist(),
        "dynamic_equity": df_bt['Dynamic_Equity'].round(2).tolist(),
        "turbulent_prob": df_bt['Turbulent_Prob'].round(4).tolist(),
        "weights": weights.round(4).tolist()
    }

    return {
        "static_stats": compute_stats(simple_asset_returns, df_bt['Static_Equity']),
        "dynamic_stats": compute_stats(df_bt['Strategy_Return'], df_bt['Dynamic_Equity']),
        "chart_data": chart_data
    }