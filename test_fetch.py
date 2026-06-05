import pandas as pd
import yfinance as yf
import warnings
warnings.filterwarnings('ignore')

last_date = pd.to_datetime('2026-05-29')
today = pd.to_datetime('today').normalize()

tickers = {
    'USDIDR': 'IDR=X', 'DXY': 'DX-Y.NYB', 'BRENT': 'BZ=F', 
    'GOLD': 'GC=F', 'VIX': '^VIX', 'IHSG': '^JKSE', 
    'US10Y': '^TNX', 'SP500': '^GSPC'
}

start_fetch = (last_date + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
end_fetch = (today + pd.Timedelta(days=1)).strftime('%Y-%m-%d')

print(f"Fetching from {start_fetch} to {end_fetch}")

new_data = pd.DataFrame()
for col, ticker in tickers.items():
    try:
        t_data = yf.download(ticker, start=start_fetch, end=end_fetch, progress=False)
        if not t_data.empty:
            if isinstance(t_data.columns, pd.MultiIndex):
                # Usually ('Close', 'IDR=X')
                if 'Close' in t_data.columns.get_level_values(0):
                    series = t_data['Close'].iloc[:, 0]
                else:
                    series = t_data.iloc[:, 0]
            elif 'Close' in t_data.columns:
                series = t_data['Close']
            else:
                series = t_data.iloc[:, 0]
            new_data[col] = series
    except Exception as e:
        print(f"Failed {ticker}: {e}")

print("Raw downloaded:")
print(new_data)

if not new_data.empty:
    new_data = new_data.reset_index()
    if 'index' in new_data.columns:
        new_data.rename(columns={'index': 'Date'}, inplace=True)
    new_data['Date'] = new_data['Date'].dt.tz_localize(None)
    new_data = new_data.dropna(subset=['USDIDR'])
    new_data.ffill(inplace=True)
    print("Processed:")
    print(new_data)
