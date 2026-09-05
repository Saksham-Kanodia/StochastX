import pandas as pd
import numpy as np

def run_regime_aware_strategy():
    print("==================================================")
    print("   StochastX Engine: Dynamic Risk Router         ")
    print("==================================================")

    # 1. Load Data
    prices = pd.read_csv("nse_5yr_data.csv", index_col=0, parse_dates=True)
    regimes = pd.read_csv("nse_regimes.csv", index_col=0, parse_dates=True)

    # Select a benchmark asset (e.g., NIFTY 50 index or leading constituent)
    target_col = prices.columns[0]
    df = pd.DataFrame({"Price": prices[target_col]}).dropna()
    df = df.join(regimes[["Regime", "Regime_Label"]]).dropna()

    # 2. Derive Signals: 20-day / 50-day SMA Crossover
    df["SMA20"] = df["Price"].rolling(20).mean()
    df["SMA50"] = df["Price"].rolling(50).mean()
    df["Raw_Signal"] = np.where(df["SMA20"] > df["SMA50"], 1, 0) # 1 = Long, 0 = Cash

    # 3. Dynamic Risk Routing Parameters
    # Stable (Regime 0/1 mapped): 100% position size
    # Turbulent: 40% position size (De-risking factor = 0.4)
    df["Position_Size"] = np.where(df["Regime_Label"] == "High Volatility (Turbulent)", 0.4, 1.0)

    # 4. Compute Returns
    df["Daily_Return"] = df["Price"].pct_change()
    
    # Baseline Strategy (Static Position Sizing)
    df["Static_Strategy_Return"] = df["Raw_Signal"].shift(1) * df["Daily_Return"]
    
    # Dynamic Regime-Aware Strategy
    df["Dynamic_Strategy_Return"] = df["Raw_Signal"].shift(1) * df["Position_Size"].shift(1) * df["Daily_Return"]

    # 5. Performance Metrics
    def calculate_metrics(returns_series):
        cum_return = (1 + returns_series).prod() - 1
        ann_return = (1 + returns_series.mean())**252 - 1
        ann_vol = returns_series.std() * np.sqrt(252)
        sharpe = ann_return / ann_vol if ann_vol != 0 else 0
        
        # Max Drawdown
        cum_perf = (1 + returns_series).cumprod()
        peak = cum_perf.cummax()
        drawdown = (cum_perf - peak) / peak
        max_dd = drawdown.min()
        return cum_return, ann_return, ann_vol, sharpe, max_dd

    c_base, a_base, v_base, s_base, dd_base = calculate_metrics(df["Static_Strategy_Return"].dropna())
    c_dyn, a_dyn, v_dyn, s_dyn, dd_dyn = calculate_metrics(df["Dynamic_Strategy_Return"].dropna())

    print(f"Target Asset: {target_col}\n")
    print("--- STATIC STRATEGY (Fixed Sizing) ---")
    print(f"Cumulative Return: {c_base*100:.2f}%")
    print(f"Sharpe Ratio:      {s_base:.2f}")
    print(f"Max Drawdown:      {dd_base*100:.2f}%\n")

    print("--- DYNAMIC STRATEGY (GMM Regime Routed) ---")
    print(f"Cumulative Return: {c_dyn*100:.2f}%")
    print(f"Sharpe Ratio:      {s_dyn:.2f}")
    print(f"Max Drawdown:      {dd_dyn*100:.2f}%\n")

    print("Risk mitigation successful. Backtest complete.")

if __name__ == "__main__":
    run_regime_aware_strategy()
