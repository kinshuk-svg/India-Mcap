"""Builds data.json: daily total market cap (Rs lakh crore) of Nifty Total Market constituents.
Method: close price x shares outstanding, summed across all constituents (constituents fixed as of today).
This version also prints a DIAGNOSTICS block in the log to help find why totals differ from NSE."""
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

# 2. Shares outstanding (cached). Anything missing or failed earlier is retried every run.
shares = json.load(open(SHARES_FILE)) if os.path.exists(SHARES_FILE) else {}
for t in tickers:
    if shares.get(t):
        continue
    val = None
    try:
        val = yf.Ticker(t).fast_info.get("shares")
    except Exception:
        pass
    if not val:
        try:
            val = yf.Ticker(t).info.get("sharesOutstanding")
        except Exception:
            pass
    shares[t] = val
json.dump(shares, open(SHARES_FILE, "w"))
missing = [t for t in tickers if not shares.get(t)]

# 3. Prices (auto_adjust=False -> split/bonus adjusted, NOT dividend adjusted)
px_all = yf.download(tickers, start=START, auto_adjust=False, progress=False)["Close"]
px_all = px_all.ffill()               # carry last price through suspensions
sh = pd.Series({t: shares[t] for t in tickers if shares.get(t)})
px = px_all[sh.index.intersection(px_all.columns)]

# 4. Sum: price x shares, in Rs lakh crore (1 lakh crore = 1e12)
mcap = (px * sh[px.columns]).sum(axis=1, min_count=1) / 1e12
mcap = mcap.dropna()

json.dump({
    "updated": dt.datetime.utcnow().strftime("%Y-%m-%d"),
    "constituents": len(tickers),
    "dates": [d.strftime("%Y-%m-%d") for d in mcap.index],
    "mcap": [round(float(v), 2) for v in mcap.values],
}, open("data.json", "w"))

# 5. Diagnostics (read this in the Actions log)
last = px.iloc[-1]
tbl = pd.DataFrame({"price": last, "shares_crore": sh[px.columns] / 1e7})
tbl["mcap_lakh_cr"] = tbl["price"] * tbl["shares_crore"] * 1e7 / 1e12
tbl = tbl.sort_values("mcap_lakh_cr", ascending=False)
no_price = [t for t in tickers if t not in px_all.columns or pd.isna(px_all[t].iloc[-1])]
print("=== DIAGNOSTICS ===")
print("Latest date in data:", px.index[-1].date())
print("Stocks in index list:", len(tickers))
print("Stocks with a share count:", len(sh))
print("Stocks with NO share count:", len(missing))
print("Stocks with NO latest price:", len(no_price))
print("Total (before 96.5% switch), lakh crore:", round(float(tbl["mcap_lakh_cr"].sum()), 1))
print("--- Top 15 by market cap ---")
print(tbl.head(15).round(2).to_string())
print("--- No share count ---")
print(missing)
print("--- No latest price ---")
print(no_price)
