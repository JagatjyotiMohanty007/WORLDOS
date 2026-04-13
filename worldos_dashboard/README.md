# ⚡ World OS — Live Float Dashboard

**POC v1.0 · Jagatjyoti Mohanty · Roll 38/2025 · XLRI CXO Batch 4**

> "The money to fix the world already exists. We are just building the pipe."

---

## 🚀 Quick Start (Local — 3 Commands)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run dashboard
streamlit run dashboard.py

# 3. Open browser → http://localhost:8501
```

---

## 🌐 Deploy to Production (Railway — Free Tier)

### Option A: Railway (Recommended — 1 click)

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Create new project and deploy
railway init
railway up

# Get your live URL
railway open
```

Your dashboard will be live at: `https://worldos-dashboard-<id>.railway.app`

---

### Option B: Render (Free Tier)

1. Push this folder to a GitHub repository
2. Go to [render.com](https://render.com) → New Web Service
3. Connect your GitHub repo
4. Set:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `streamlit run dashboard.py --server.port=$PORT --server.address=0.0.0.0`
5. Click Deploy → Live in ~2 minutes

---

### Option C: Streamlit Cloud (Easiest — Free)

1. Push to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect repo → Select `dashboard.py` → Deploy

---

### Option D: Docker (Any Server/VPS)

```bash
# Build image
docker build -t worldos-dashboard .

# Run container
docker run -p 8501:8501 worldos-dashboard

# With environment variables
docker run -p 8501:8501 \
  -e CCAVENUE_API_KEY=your_key \
  -e GROWW_API_KEY=your_key \
  worldos-dashboard
```

---

## 🔌 Connecting Real APIs (Production Mode)

### CCAvenue Settlement API
Replace `FloatEngine.get_state()` with:

```python
import requests

def get_real_float_data(merchant_id: str, api_key: str) -> FloatState:
    """
    CCAvenue Settlement Report API
    Docs: https://developer.ccavenue.com/docs/settlement
    """
    response = requests.post(
        "https://api.ccavenue.com/apis/servlet/DoWebTrans",
        data={
            "enc_request": encrypt_request(merchant_id, api_key),
            "access_code": api_key,
            "command": "getSettlementReport",
        }
    )
    data = parse_ccavenue_response(response.text)
    return FloatState(
        total_float=float(data["total_settlement_amount"]),
        in_settlement=float(data["pending_settlement"]),
        in_bank=float(data["settled_amount"]),
        daily_sales=float(data["today_sales"]),
    )
```

### Groww Liquid Fund API
Replace `FloatEngine.get_fund_prices()` with:

```python
def get_real_fund_nav() -> dict:
    """
    AMFI India NAV API (Free, no auth required)
    Docs: https://www.amfiindia.com/research-information/other-data/nav-history
    """
    # AMFI all fund NAVs
    response = requests.get("https://api.mfapi.in/mf/119533")  # Nippon Liquid
    data = response.json()
    return {
        "Nippon Liquid Fund": {
            "nav": float(data["data"][0]["nav"]),
            "rate": 7.2,
            "risk": "LOW"
        }
    }
```

### Auto-Investment via Zerodha Coin API
```python
def auto_invest_float(amount: float, fund_id: str, api_key: str):
    """
    Zerodha Coin API for liquid fund investment
    Docs: https://kite.trade/docs/connect/v3/
    """
    from kiteconnect import KiteConnect
    kite = KiteConnect(api_key=api_key)
    
    # Place SIP order
    order_id = kite.place_mf_order(
        tradingsymbol=fund_id,
        transaction_type=kite.TRANSACTION_TYPE_BUY,
        amount=amount,
        tag="worldos_float_yield"
    )
    return order_id
```

---

## 🗃️ Database Setup (Supabase — Production)

```python
# Install: pip install supabase
from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Store yield record
def log_yield(merchant_id: str, amount: float, yield_earned: float):
    supabase.table("yield_history").insert({
        "merchant_id": merchant_id,
        "float_amount": amount,
        "yield_earned": yield_earned,
        "timestamp": datetime.now().isoformat(),
    }).execute()

# Get history
def get_yield_history(merchant_id: str, days: int = 30):
    return supabase.table("yield_history") \
        .select("*") \
        .eq("merchant_id", merchant_id) \
        .gte("timestamp", (datetime.now() - timedelta(days=days)).isoformat()) \
        .execute()
```

---

## 🤖 AI Agent Integration (Claude API)

```python
import anthropic

def run_problem_scanner() -> list:
    """Agent 2: Scans for solvable problems weekly"""
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": """Scan for the top 5 most solvable local problems in Hyderabad, India
            that could be solved with ₹50,000 or less. For each problem provide:
            - Problem description
            - Population affected
            - Estimated cost to solve
            - Solution approach
            Return as JSON array."""
        }]
    )
    return json.loads(message.content[0].text)
```

---

## 📁 File Structure

```
worldos_dashboard/
├── dashboard.py          ← Main Streamlit app (THIS FILE)
├── requirements.txt      ← Python dependencies
├── Procfile              ← Railway/Heroku deployment
├── Dockerfile            ← Docker deployment
├── .streamlit/
│   └── config.toml       ← Streamlit dark theme config
└── README.md             ← This file
```

---

## 🔐 Environment Variables

Create `.env` file for production:

```env
CCAVENUE_MERCHANT_ID=your_merchant_id
CCAVENUE_API_KEY=your_api_key
CCAVENUE_WORKING_KEY=your_working_key
GROWW_API_KEY=your_groww_key
ZERODHA_API_KEY=your_zerodha_key
ZERODHA_SECRET=your_zerodha_secret
ANTHROPIC_API_KEY=your_claude_key
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_KEY=your_supabase_anon_key
```

---

## 📊 Dashboard Features

| Feature | Status | Description |
|---------|--------|-------------|
| Float Tracker | ✅ Live | Real-time settlement float monitoring |
| Yield Calculator | ✅ Live | Compound yield projections |
| Settlement Countdown | ✅ Live | Per-transaction timers |
| Idle Cash Alert | ✅ Live | Daily cost of inaction |
| Fund NAV Display | ✅ Live | 5 recommended liquid funds |
| Scale Simulator | ✅ Live | Project yield at any merchant count |
| Revenue Projections | ✅ Live | 5-year financial charts |
| Agent Activity Log | ✅ Live | AI agent action feed |
| Auto-Refresh | ✅ Live | Updates every 30 seconds |
| CCAvenue Integration | 🔄 Month 2 | Live API connection |
| Auto-Investment | 🔄 Month 2 | Groww/Zerodha Coin API |
| Database Storage | 🔄 Month 2 | Supabase yield history |
| Multi-Merchant | 🔄 Month 3 | Multiple gateway support |

---

*World OS Technologies · Confidential · 2026*
*Roll No. 38/2025 · CXO Batch 4 · XLRI Jamshedpur*
