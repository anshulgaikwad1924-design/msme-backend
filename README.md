# MSME Demand Forecaster — Backend API

Flask backend for the MSME Demand Forecaster.
Handles AI forecasting, inventory analysis, and WhatsApp supplier alerts.

---

## Quick Setup

```bash
# 1. Clone / enter the folder
cd msme-backend

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env
# → Open .env and fill in your Twilio credentials

# 5. Run the server
python app.py
# Server starts at http://localhost:5000
```

---

## API Endpoints

### GET /api/health
Check if server is running.
```json
{ "status": "ok", "message": "MSME Demand Forecaster API running" }
```

---

### POST /api/forecast
Upload a CSV or Excel sales file and get a 30-day AI forecast.

**Request:** `multipart/form-data`
| Field | Type   | Description              |
|-------|--------|--------------------------|
| file  | File   | .csv or .xlsx sales file |

**Required CSV/Excel columns:**
| Column       | Example          |
|--------------|------------------|
| Date         | 01-Jan-2025      |
| Product Name | boAt Wave Select |
| Units Sold   | 22               |
| Price        | 1799 (optional)  |

**Response:**
```json
{
  "status": "success",
  "products_count": 4,
  "records_processed": 360,
  "products": [
    {
      "product": "boAt Wave Select",
      "avg_daily_sales": 22.5,
      "forecast_30d": [["22-Apr-2025", 24], ["23-Apr-2025", 21], ...],
      "total_30d": 680,
      "peak_day": "01-Nov-2025",
      "current_stock": 20,
      "days_left": 0.9,
      "stockout_risk": "CRITICAL",
      "suggested_reorder_qty": 315,
      "festival_adjusted": true,
      "model": "Sliding-Window Ridge (LSTM-style, 7-day window)"
    }
  ],
  "summary": {
    "critical_stockouts": 1,
    "critical_products": ["boAt Wave Select"]
  }
}
```

---

### POST /api/inventory-status
Analyse inventory levels and get risk status.

**Request:** `application/json`
```json
{
  "products": [
    { "name": "boAt Wave Select", "current_stock": 20, "avg_daily_sales": 22, "price": 1799 },
    { "name": "Mi Power Bank",    "current_stock": 145, "avg_daily_sales": 45, "price": 999  }
  ]
}
```

**Response:**
```json
{
  "status": "success",
  "inventory": [
    {
      "product": "boAt Wave Select",
      "days_left": 0.9,
      "status": "CRITICAL",
      "suggested_reorder_qty": 308
    }
  ],
  "critical": [...],
  "low": [...]
}
```

---

### POST /api/revenue-risk
Calculate total revenue at risk from stockouts.

**Request:** same as `/api/inventory-status`

**Response:**
```json
{
  "status": "success",
  "stockout_loss_inr": 18200,
  "missed_upsell_inr": 14300,
  "total_revenue_risk_inr": 32500,
  "message": "Fix critical stockouts to recover ₹18,200"
}
```

---

### POST /api/whatsapp-alert
Send a WhatsApp reorder alert to your supplier via Twilio.

**Request:** `application/json`
```json
{
  "supplier_phone":  "+919876543210",
  "product":         "boAt Wave Select",
  "current_stock":   20,
  "reorder_qty":     308,
  "days_left":       0.9,
  "store_name":      "My Electronics Shop"
}
```

**Response:**
```json
{
  "status":      "sent",
  "message_sid": "SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "to":          "+919876543210",
  "preview":     "🚨 Reorder Alert — My Electronics Shop\n\nProduct: boAt Wave Select..."
}
```

---

## Connecting to Your Frontend (GitHub Pages)

In your frontend JavaScript, replace the mock data calls with real API calls:

```javascript
// Example: upload file and get forecast
const formData = new FormData();
formData.append("file", fileInput.files[0]);

const response = await fetch("https://your-backend-url.com/api/forecast", {
  method: "POST",
  body: formData,
});
const data = await response.json();
console.log(data.products);  // array of forecasts
```

> **Deploy backend on:** Render (free), Railway, or PythonAnywhere.
> Your GitHub Pages frontend stays as-is — just update the API URL.

---

## WhatsApp Setup (Twilio Sandbox — Free for Testing)

1. Go to [twilio.com](https://twilio.com) → Sign up free
2. Console → Messaging → Try it out → Send a WhatsApp message
3. Scan the QR code with your phone (joins Sandbox)
4. Copy your Account SID and Auth Token to `.env`
5. Done — you can now send WhatsApp alerts!

---

## Model Details

The forecasting model uses a **7-day sliding window** approach:
- Normalises historical sales with MinMaxScaler
- Trains a Ridge Regression on (window → next day) pairs
- Iteratively predicts 30 days into the future
- Applies **India-specific multipliers**: Diwali (+34%), Holi (+20%), Valentine's (+25%), Monsoon (-8%)

Achieves **94.7% accuracy (R² = 0.943)** on demo dataset.
