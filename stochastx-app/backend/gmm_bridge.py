import sys
import json
import pandas as pd
import numpy as np
from sklearn.mixture import GaussianMixture

def run_gmm():
    csv_path = sys.argv[1]
    asset = sys.argv[2]
    
    df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
    series = df[asset].dropna()
    
    log_returns = np.log(series / series.shift(1)).dropna()
    rolling_vol = log_returns.rolling(window=15).std().dropna()
    
    feature_matrix = pd.concat([log_returns, rolling_vol], axis=1).dropna()
    feature_matrix.columns = ["log_return", "rolling_vol"]
    
    gmm = GaussianMixture(n_components=2, covariance_type="full", random_state=42)
    regimes = gmm.fit_predict(feature_matrix)
    feature_matrix["Regime"] = regimes
    
    regime_0_vol = feature_matrix[feature_matrix["Regime"] == 0]["rolling_vol"].mean()
    regime_1_vol = feature_matrix[feature_matrix["Regime"] == 1]["rolling_vol"].mean()
    high_vol_id = 0 if regime_0_vol > regime_1_vol else 1
    
    labels = ["High Volatility (Turbulent)" if r == high_vol_id else "Low Volatility (Stable)" for r in regimes]
    
    output = {
        "dates": [str(d.date()) for d in feature_matrix.index],
        "prices": series.loc[feature_matrix.index].tolist(),
        "regimes": labels
    }
    
    print(json.dumps(output))

if __name__ == "__main__":
    run_gmm()
