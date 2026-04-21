import pandas as pd
import numpy as np
from io import BytesIO
from sklearn.preprocessing import MinMaxScaler
from sklearn.linear_model import Ridge
from datetime import date, timedelta

# ── Festival calendar (India) ─────────────────────────────
FESTIVAL_IMPACT = {
    "diwali":       {"months": [10, 11], "boost": 1.34},
    "holi":         {"months": [3],      "boost": 1.20},
    "navratri":     {"months": [10],     "boost": 1.18},
    "eid":          {"months": [3, 4],   "boost": 1.15},
    "christmas":    {"months": [12],     "boost": 1.22},
    "valentine":    {"months": [2],      "boost": 1.25},
    "independence": {"months": [8],      "boost": 1.10},
}

MONSOON_MONTHS = [6, 7, 8, 9]
MONSOON_DROP   = 0.92   # -8% footfall


def _festival_multiplier(month: int) -> float:
    mult = 1.0
    for info in FESTIVAL_IMPACT.values():
        if month in info["months"]:
            mult = max(mult, info["boost"])
    if month in MONSOON_MONTHS:
        mult *= MONSOON_DROP
    return round(mult, 3)


def _read_file(file_obj) -> pd.DataFrame:
    """Read CSV or Excel file into DataFrame."""
    filename = file_obj.filename.lower()
    raw = file_obj.read()
    if filename.endswith(".csv"):
        df = pd.read_csv(BytesIO(raw))
    else:
        df = pd.read_excel(BytesIO(raw))
    return df


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Map common column name variants to standard names."""
    rename = {}
    for col in df.columns:
        low = col.strip().lower()
        if "date" in low:
            rename[col] = "date"
        elif "product" in low and "name" in low:
            rename[col] = "product"
        elif "unit" in low and "sold" in low:
            rename[col] = "units_sold"
        elif "unit" in low:
            rename[col] = "units_sold"
        elif "qty" in low or "quantity" in low:
            rename[col] = "units_sold"
        elif "price" in low or "selling" in low:
            rename[col] = "price"
        elif "revenue" in low:
            rename[col] = "revenue"
        elif "stock" in low and "open" in low:
            rename[col] = "opening_stock"
        elif "stock" in low and "clos" in low:
            rename[col] = "closing_stock"
    df = df.rename(columns=rename)
    return df


# ── LSTM-style sliding window model ───────────────────────
WINDOW = 7   # 7-day lookback window

def _build_sequences(series: np.ndarray, window: int):
    X, y = [], []
    for i in range(len(series) - window):
        X.append(series[i : i + window])
        y.append(series[i + window])
    return np.array(X), np.array(y)


def _train_and_forecast(daily_series: list, horizon: int = 30) -> list:
    """
    Sliding-window Ridge Regression model (LSTM-style architecture).
    Uses a 7-day lookback window, normalised inputs.
    Returns `horizon` future predictions as a list of floats.
    """
    arr = np.array(daily_series, dtype=float).reshape(-1, 1)
    scaler = MinMaxScaler()
    scaled = scaler.fit_transform(arr).flatten()

    X, y = _build_sequences(scaled, WINDOW)
    if len(X) < 5:
        # Not enough data — return rolling mean
        mean = float(np.mean(daily_series[-7:]))
        return [round(mean) for _ in range(horizon)]

    model = Ridge(alpha=1.0)
    model.fit(X, y)

    # Iterative forecast
    window_buf = list(scaled[-WINDOW:])
    preds_scaled = []
    for _ in range(horizon):
        x_in = np.array(window_buf[-WINDOW:]).reshape(1, -1)
        p = model.predict(x_in)[0]
        preds_scaled.append(p)
        window_buf.append(p)

    preds = scaler.inverse_transform(
        np.array(preds_scaled).reshape(-1, 1)
    ).flatten()

    return [max(0, round(float(v))) for v in preds]


# ── Public functions called by app.py ─────────────────────

def forecast_demand(file_obj) -> dict:
    df = _read_file(file_obj)
    df = _normalise_columns(df)

    required = {"date", "product", "units_sold"}
    missing  = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns in your file: {missing}. "
                         f"Found: {list(df.columns)}")

    df["date"]       = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
    df["units_sold"] = pd.to_numeric(df["units_sold"], errors="coerce").fillna(0)
    df               = df.dropna(subset=["date"]).sort_values("date")

    # Detect price column if present
    has_price = "price" in df.columns

    products    = df["product"].unique().tolist()
    today       = date.today()
    forecast_dates = [(today + timedelta(days=i)).strftime("%d-%b-%Y")
                      for i in range(1, 31)]

    results = []
    for prod in products:
        sub       = df[df["product"] == prod].sort_values("date")
        daily     = sub["units_sold"].tolist()
        avg_price = float(sub["price"].mean()) if has_price else 0.0

        raw_forecast = _train_and_forecast(daily, horizon=30)

        # Apply festival & monsoon multipliers
        adjusted = []
        for i, val in enumerate(raw_forecast):
            fdate = today + timedelta(days=i + 1)
            mult  = _festival_multiplier(fdate.month)
            adjusted.append(max(0, round(val * mult)))

        avg_daily      = round(float(np.mean(daily[-14:])), 1) if daily else 0
        total_30d      = sum(adjusted)
        peak_day_idx   = int(np.argmax(adjusted))
        peak_day_units = adjusted[peak_day_idx]

        # Stockout detection
        closing_stocks = sub["closing_stock"].tolist() if "closing_stock" in sub else []
        current_stock  = int(closing_stocks[-1]) if closing_stocks else None
        days_left      = round(current_stock / avg_daily, 1) if (current_stock and avg_daily > 0) else None
        stockout_risk  = "CRITICAL" if (days_left and days_left <= 3) else \
                         "LOW"      if (days_left and days_left <= 7) else "OK"

        results.append({
            "product":         prod,
            "avg_daily_sales": avg_daily,
            "forecast_30d":    list(zip(forecast_dates, adjusted)),
            "total_30d":       total_30d,
            "peak_day":        forecast_dates[peak_day_idx],
            "peak_day_units":  peak_day_units,
            "current_stock":   current_stock,
            "days_left":       days_left,
            "stockout_risk":   stockout_risk,
            "suggested_reorder_qty": round(avg_daily * 14),
            "avg_price":       avg_price,
            "revenue_30d_est": round(total_30d * avg_price, 2) if avg_price else None,
            "festival_adjusted": True,
            "model":           "Sliding-Window Ridge (LSTM-style, 7-day window)",
        })

    # Summary
    critical = [r for r in results if r["stockout_risk"] == "CRITICAL"]
    low      = [r for r in results if r["stockout_risk"] == "LOW"]

    return {
        "status":         "success",
        "products_count": len(products),
        "records_processed": len(df),
        "forecast_horizon": "30 days",
        "accuracy_note":  "Model trained on your uploaded data",
        "products":       results,
        "summary": {
            "critical_stockouts": len(critical),
            "low_stock_warnings": len(low),
            "critical_products":  [r["product"] for r in critical],
        },
    }


def analyze_inventory(products: list) -> dict:
    """
    products = [
      { "name": "boAt Wave", "current_stock": 20,
        "avg_daily_sales": 22, "price": 1799 }, ...
    ]
    """
    results = []
    for p in products:
        stock   = float(p.get("current_stock", 0))
        avg     = float(p.get("avg_daily_sales", 1))
        price   = float(p.get("price", 0))
        days_left = round(stock / avg, 1) if avg > 0 else 999

        if days_left <= 3:
            status = "CRITICAL"
        elif days_left <= 7:
            status = "LOW"
        else:
            status = "OK"

        results.append({
            "product":       p.get("name"),
            "current_stock": int(stock),
            "avg_daily_sales": avg,
            "days_left":     days_left,
            "reorder_point": round(avg * 3),
            "suggested_reorder_qty": round(avg * 14),
            "status":        status,
            "price":         price,
        })

    return {
        "status":    "success",
        "inventory": results,
        "critical":  [r for r in results if r["status"] == "CRITICAL"],
        "low":       [r for r in results if r["status"] == "LOW"],
    }


def calculate_revenue_risk(products: list) -> dict:
    """Calculate revenue at risk from stockouts."""
    stockout_loss   = 0.0
    missed_upsell   = 0.0
    risk_breakdown  = []

    for p in products:
        stock    = float(p.get("current_stock", 0))
        avg      = float(p.get("avg_daily_sales", 1))
        price    = float(p.get("price", 0))
        days_left = round(stock / avg, 1) if avg > 0 else 999

        if days_left < 7:
            # Units that can't be sold this week due to stockout
            days_out    = max(0, 7 - days_left)
            lost_units  = avg * days_out
            lost_rev    = lost_units * price
            upsell      = lost_rev * 0.15   # 15% upsell assumption

            stockout_loss  += lost_rev
            missed_upsell  += upsell

            risk_breakdown.append({
                "product":     p.get("name"),
                "days_left":   days_left,
                "days_out_of_stock": round(days_out, 1),
                "lost_units":  round(lost_units),
                "stockout_loss_inr": round(lost_rev, 2),
                "missed_upsell_inr": round(upsell, 2),
            })

    total_risk = stockout_loss + missed_upsell

    return {
        "status":             "success",
        "stockout_loss_inr":  round(stockout_loss, 2),
        "missed_upsell_inr":  round(missed_upsell, 2),
        "total_revenue_risk_inr": round(total_risk, 2),
        "risk_breakdown":     risk_breakdown,
        "message":            f"Fix critical stockouts to recover ₹{round(stockout_loss):,}",
    }
