import numpy as np
import pandas as pd
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import RobustScaler


def generate_regime_signals(
    df: pd.DataFrame, target_asset: str, calibration_window: int = 252
) -> pd.DataFrame:
    """Extracts features, fits RobustScaler & GMM strictly on in-sample data,

    and returns features with lagged execution probabilities.
    """
    if target_asset not in df.columns:
        raise KeyError(
            f"Target asset '{target_asset}' not found in DataFrame columns."
        )

    prices = df[target_asset].dropna()

    # 1. Stationary log returns and annualized exponential volatility
    log_returns = np.log(prices / prices.shift(1))
    rolling_vol = log_returns.ewm(span=15).std() * np.sqrt(252)

    features = pd.DataFrame(
        {'return': log_returns, 'volatility': rolling_vol}
    ).dropna()

    # 2. Fit Scaler ONLY on In-Sample calibration period (Issue 1 Fix)
    scaler = RobustScaler()
    in_sample_data = features.iloc[:calibration_window]
    scaler.fit(in_sample_data)

    scaled_features = pd.DataFrame(
        scaler.transform(features),
        index=features.index,
        columns=features.columns,
    )

    # 3. Fit GMM ONLY on In-Sample scaled features (Issue 1 Fix)
    gmm = GaussianMixture(
        n_components=2, covariance_type='full', n_init=10, random_state=42
    )
    gmm.fit(scaled_features.iloc[:calibration_window])

    # 4. Map high volatility cluster index dynamically
    vol_idx = scaled_features.columns.get_loc('volatility')
    high_vol_cluster = (
        1 if gmm.means_[1][vol_idx] > gmm.means_[0][vol_idx] else 0
    )

    # 5. Out-of-sample probability inference across the time horizon
    probs = gmm.predict_proba(scaled_features)
    raw_turbulent_prob = pd.Series(
        probs[:, high_vol_cluster], index=scaled_features.index
    )

    # 6. Apply low-pass filter (EWM span=5) and 1-day execution lag
    features['Turbulent_Prob'] = raw_turbulent_prob.ewm(span=5).mean()
    features['Regime'] = np.where(
        features['Turbulent_Prob'] > 0.50,
        'High Volatility (Turbulent)',
        'Low Volatility (Stable)',
    )
    features['Execution_Prob'] = features['Turbulent_Prob'].shift(1).fillna(0)

    return features


def run_backtest(
    features: pd.DataFrame,
    derisk_factor: float = 0.40,
    annual_rf: float = 0.065,
    fee_bps: float = 5.0,
) -> tuple[dict, dict, pd.DataFrame]:
    """Vectorized backtest engine with simple returns, cash yield, and transaction friction."""
    # Defensive copy prevents side-effect mutations (Issue 4 Fix)
    df_bt = features.copy()

    # 1. Dynamic position weights based on lagged probability
    weights = 1.0 - (df_bt['Execution_Prob'] * (1.0 - derisk_factor))

    # 2. Convert log returns to simple daily asset returns
    simple_asset_returns = np.exp(df_bt['return']) - 1.0

    # 3. Linear daily risk-free rate eliminates arithmetic drag (Issue 3 Fix)
    daily_rf = annual_rf / 252.0

    # 4. Explicit Basis Point Fee Conversion: 5.0 bps -> 0.0005 ratio (Issue 2 Fix)
    fee_ratio = fee_bps / 10000.0
    weight_turnover = weights.diff().abs().fillna(0)
    transaction_costs = weight_turnover * fee_ratio

    # 5. Net Strategy Return
    df_bt['Strategy_Return'] = (
        (weights * simple_asset_returns)
        + ((1.0 - weights) * daily_rf)
        - transaction_costs
    )

    # 6. Compounded Equity Curves ($100,000 starting capital)
    initial_capital = 100000.0
    df_bt['Static_Equity'] = initial_capital * (
        1.0 + simple_asset_returns
    ).cumprod()
    df_bt['Dynamic_Equity'] = initial_capital * (
        1.0 + df_bt['Strategy_Return']
    ).cumprod()

    # 7. Performance Statistics Engine
    def calculate_stats(returns_series, equity_series):
        total_return = (
            (equity_series.iloc[-1] - initial_capital) / initial_capital
        ) * 100.0

        # Compound Annual Growth Rate (CAGR)
        n_years = len(returns_series) / 252.0
        cagr = (
            (equity_series.iloc[-1] / initial_capital) ** (1.0 / n_years) - 1.0
        ) * 100.0

        mean_ret = returns_series.mean() * 252.0
        vol_ret = returns_series.std() * np.sqrt(252)
        sharpe = (mean_ret - annual_rf) / vol_ret if vol_ret > 0 else 0.0

        rolling_peak = equity_series.cummax()
        drawdowns = (equity_series - rolling_peak) / rolling_peak
        max_dd = drawdowns.min() * 100.0

        return {
            'total_return': round(total_return, 2),
            'cagr': round(cagr, 2),
            'sharpe': round(sharpe, 2),
            'max_drawdown': round(max_dd, 2),
        }

    static_stats = calculate_stats(
        simple_asset_returns, df_bt['Static_Equity']
    )
    dynamic_stats = calculate_stats(
        df_bt['Strategy_Return'], df_bt['Dynamic_Equity']
    )

    return static_stats, dynamic_stats, df_bt


# --- EXAMPLE USAGE ---
df = pd.read_csv("nse_5yr_data.csv", index_col=0, parse_dates=True)
signals_df = generate_regime_signals(
    df, target_asset="AXISBANK.NS", calibration_window=252
)

# 2. Execute backtest
static_metrics, dynamic_metrics, full_backtest_df = run_backtest(
    signals_df, derisk_factor=0.40, annual_rf=0.065, fee_bps=5.0
)