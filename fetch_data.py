import yfinance as yf
import pandas as pd

# Define 4 top liquid NSE banking tickers
tickers = [
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "AXISBANK.NS",
    "KOTAKBANK.NS"
]

print("==================================================")
print("   StochastX Data Engine: Downloading NSE Data    ")
print("==================================================")

# Disable multi-threading and caching to prevent Windows SQLite database locks
print(f"Downloading 5 years of daily data for: {', '.join(tickers)}...")
raw_data = yf.download(tickers, period="5y", threads=False)['Close']

# Clean Missing Data
df = raw_data.ffill().bfill().dropna()

# Save locally to CSV
csv_filename = "nse_5yr_data.csv"
df.to_csv(csv_filename)

print("\n--- Data Download Complete ---")
print(f"Total Trading Days: {len(df)}")
print(f"Date Range:         {df.index[0].strftime('%Y-%m-%d')} to {df.index[-1].strftime('%Y-%m-%d')}")
print(f"Saved File:         '{csv_filename}'\n")

print("--- Latest Stock Prices (in ₹) ---")
latest = df.iloc[-1]
for t in tickers:
    print(f"{t.replace('.NS', ''):12s}: ₹{latest[t]:.2f}")