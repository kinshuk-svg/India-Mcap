"""Builds data.json: daily total market cap (Rs lakh crore) of Nifty Total Market constituents.
Method: close price x shares outstanding, summed across all constituents (constituents fixed as of today)."""
import io, json, os, datetime as dt
import pandas as pd, requests, yfinance as yf

CSV_URL = "https://niftyindices.com/IndexConstituent/ind_niftytotalmarket_list.csv"
START = "2020-01-01"
SHARES_FILE = "shares.json"   # cache, committed to the repo
UA = {"User-Agent": "Mozilla/5.0"}

# 1. Constituents
r = requests.get(CSV_URL, headers=UA, timeout=30); r.raise_for_status()
symbols = pd.read_csv(io.StringIO(r.text))["Symbol"].str.strip().tolist()
tickers = [s + ".NS" for s in symbols]
print(f"{len(tickers)} constituents")

# 2. Shares outstanding (cached; only fetch the missing ones)
shares = json.load(open(SHARES_FILE)) if os.path.exists(SHARES_FILE) else {}
for t in tickers:
    if t not in shares:
        try:
            shares[t] = yf.Ticker(t).fast_info.get("shares")
        except Exception as e:
            shares[t] = None
json.dump(shares, open(SHARES_FILE, "w"))
missing = [t for t in tickers if not shares.get(t)]
print(f"{len(missing)} tickers without share count: {missing[:20]}")

# 3. Prices (auto_adjust=False -> split/bonus adjusted, NOT dividend adjusted)
px = yf.download(tickers, start=START, auto_adjust=False, progress=False)["Close"]
px = px.ffill()                       # carry last price through suspensions
sh = pd.Series({t: shares[t] for t in tickers if shares.get(t)})
px = px[sh.index.intersection(px.columns)]

# 4. Sum: price x shares, in Rs lakh crore (1 lakh crore = 1e12)
mcap = (px * sh[px.columns]).sum(axis=1, min_count=1) / 1e12
mcap = mcap.dropna()

json.dump({
    "updated": dt.datetime.utcnow().strftime("%Y-%m-%d"),
    "constituents": len(tickers),
    "dates": [d.strftime("%Y-%m-%d") for d in mcap.index],
    "mcap": [round(float(v), 2) for v in mcap.values],
}, open("data.json", "w"))
print("Latest:", mcap.index[-1].date(), round(float(mcap.iloc[-1]), 1), "lakh crore")
