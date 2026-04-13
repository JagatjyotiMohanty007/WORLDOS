"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          WORLD OS  ·  LIVE FLOAT DASHBOARD  ·  POC v1.0                    ║
║          Jagatjyoti Mohanty  |  Roll 38/2025  |  XLRI CXO Batch 4          ║
╚══════════════════════════════════════════════════════════════════════════════╝

Run:
    pip install streamlit plotly pandas requests python-dotenv
    streamlit run dashboard.py

Deploy (Railway / Render):
    Add requirements.txt  →  railway up  OR  git push to Render

Architecture:
    ┌────────────────────────────────────────────────────────────┐
    │  Streamlit Frontend (this file)                            │
    │    ↕ live data every 30s (auto-refresh)                   │
    │  FloatEngine  ─→  CCAvenue mock / real API                 │
    │  YieldEngine  ─→  Liquid Fund calculations                 │
    │  AgentBus     ─→  Claude API for problem scanning          │
    │  DataStore    ─→  SQLite (local) / Supabase (production)   │
    └────────────────────────────────────────────────────────────┘
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import time
import json
import math
import random
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Optional
import os

# ─── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="World OS · Float Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Dark Theme CSS ────────────────────────────────────────────────────────────
st.markdown("""
<style>
  /* Global dark background */
  .stApp { background-color: #0D1B2A; color: #FFFFFF; }
  [data-testid="stSidebar"] { background-color: #132030; }
  [data-testid="metric-container"] {
      background: #132030; border: 1px solid #1A6FBF;
      border-radius: 8px; padding: 12px;
  }
  .stMetric label { color: #8AAABB !important; font-size: 11px !important; letter-spacing: 2px; }
  .stMetric [data-testid="stMetricValue"] { color: #0FB5AE !important; font-size: 28px !important; font-weight: bold; }
  div.stButton > button {
      background: #1A6FBF; color: white; border: none;
      border-radius: 6px; padding: 8px 20px; font-weight: bold;
  }
  div.stButton > button:hover { background: #0FB5AE; }
  .card {
      background: #132030; border: 1px solid #1E3045;
      border-radius: 10px; padding: 18px; margin-bottom: 12px;
  }
  .card-accent-teal  { border-left: 4px solid #0FB5AE !important; }
  .card-accent-gold  { border-left: 4px solid #F5A623 !important; }
  .card-accent-green { border-left: 4px solid #27AE60 !important; }
  .card-accent-red   { border-left: 4px solid #E74C3C !important; }
  .live-dot {
      display: inline-block; width: 10px; height: 10px;
      background: #27AE60; border-radius: 50%;
      animation: blink 1.2s infinite; margin-right: 6px;
  }
  @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.3} }
  .section-header {
      color: #1A6FBF; font-size: 13px; font-weight: bold;
      letter-spacing: 3px; text-transform: uppercase;
      border-bottom: 1px solid #1E3045; padding-bottom: 6px; margin-bottom: 14px;
  }
  .txn-row {
      background: #1A2E42; border-radius: 6px; padding: 10px 14px;
      margin: 5px 0; border-left: 3px solid;
  }
  .badge {
      display: inline-block; padding: 2px 10px; border-radius: 20px;
      font-size: 11px; font-weight: bold; margin-left: 6px;
  }
  .badge-green  { background: rgba(39,174,96,0.2);  color: #27AE60; }
  .badge-gold   { background: rgba(245,166,35,0.2); color: #F5A623; }
  .badge-red    { background: rgba(231,76,60,0.2);  color: #E74C3C; }
  .badge-blue   { background: rgba(26,111,191,0.2); color: #1A6FBF; }
  h1,h2,h3 { color: #FFFFFF !important; }
  .stSelectbox label, .stSlider label, .stNumberInput label { color: #8AAABB !important; }
  [data-testid="stDataFrame"] { background: #132030 !important; }
  footer { display: none; }
</style>
""", unsafe_allow_html=True)

# ─── Data Models ───────────────────────────────────────────────────────────────
@dataclass
class Transaction:
    txn_id: str
    amount: float
    created: datetime
    settles: datetime
    status: str = "pending"

    @property
    def hours_remaining(self) -> float:
        delta = self.settles - datetime.now()
        return max(0, delta.total_seconds() / 3600)

    @property
    def is_today(self) -> bool:
        return self.settles.date() == datetime.now().date()

    @property
    def progress(self) -> float:
        total = (self.settles - self.created).total_seconds()
        elapsed = (datetime.now() - self.created).total_seconds()
        return min(1.0, elapsed / total)


@dataclass
class FloatState:
    total_float: float = 400000.0       # ₹4 Lakh
    in_settlement: float = 150000.0     # ₹1.5 Lakh
    in_bank: float = 250000.0           # ₹2.5 Lakh
    invested_liquid: float = 97500.0    # ₹97,500
    available_float: float = 52500.0    # ₹52,500
    annual_rate: float = 0.072          # 7.2% p.a.
    daily_sales: float = 50000.0        # ₹50,000/day
    merchant_name: str = "CCAvenue · Garment Showroom"

    @property
    def daily_yield(self) -> float:
        return round(self.total_float * self.annual_rate / 365, 2)

    @property
    def idle_cash(self) -> float:
        return self.in_bank - self.invested_liquid

    @property
    def monthly_yield(self) -> float:
        return round(self.daily_yield * 30, 2)

    @property
    def projection_30d(self) -> float:
        # Compound daily
        r = self.annual_rate / 365
        return round(self.total_float * ((1 + r) ** 30 - 1), 2)

    @property
    def invested_pct(self) -> float:
        return round(self.invested_liquid / self.in_bank * 100, 1) if self.in_bank else 0


# ─── Simulated Live Data Engine ────────────────────────────────────────────────
class FloatEngine:
    """
    In production: replace simulate_* methods with real API calls to:
      - CCAvenue Settlement API  → get_settlement_data()
      - Groww / Zerodha Coin API → get_liquid_fund_nav()
      - Your database            → get_historical_yield()
    """

    def __init__(self):
        random.seed(int(time.time()) // 30)  # Changes every 30s for live feel

    def get_state(self) -> FloatState:
        # In production: fetch from CCAvenue API + database
        jitter = random.uniform(-0.02, 0.02)
        return FloatState(
            total_float=400000 * (1 + jitter),
            in_settlement=150000 * (1 + jitter * 0.5),
            in_bank=250000 * (1 - jitter * 0.3),
            invested_liquid=97500,
            available_float=52500 * (1 + jitter),
            annual_rate=0.072,
            daily_sales=50000 * (1 + random.uniform(-0.1, 0.1)),
        )

    def get_transactions(self) -> List[Transaction]:
        now = datetime.now()
        return [
            Transaction("TXN-8363", 20000, now - timedelta(hours=66), now + timedelta(hours=6)),
            Transaction("TXN-6194", 17500, now - timedelta(hours=42), now + timedelta(hours=30)),
            Transaction("TXN-8084", 12500, now - timedelta(hours=18), now + timedelta(hours=54)),
            Transaction("TXN-5521",  8000, now - timedelta(hours=2),  now + timedelta(hours=70)),
        ]

    def get_yield_history(self, days: int = 30) -> pd.DataFrame:
        """Historical yield — in production: query from database"""
        dates = [datetime.now() - timedelta(days=i) for i in range(days, 0, -1)]
        base_yield = 79
        # Simulate gradual growth as more merchants onboard
        yields = [round(base_yield * (1 + 0.02 * i/days) + random.uniform(-5, 5), 2)
                  for i in range(days)]
        float_vals = [400000 * (0.9 + 0.1 * i/days) + random.uniform(-10000, 10000)
                      for i in range(days)]
        return pd.DataFrame({"date": dates, "yield": yields, "float": float_vals})

    def get_fund_prices(self) -> dict:
        """Liquid fund NAVs — in production: fetch from AMFI API"""
        return {
            "Nippon Liquid Fund":   {"nav": round(5821.43 + random.uniform(-1, 1), 2), "rate": 7.2, "risk": "LOW"},
            "HDFC Liquid Fund":     {"nav": round(4235.18 + random.uniform(-1, 1), 2), "rate": 7.5, "risk": "LOW"},
            "Parag Parikh Liquid":  {"nav": round(1345.67 + random.uniform(-0.5, 0.5), 2), "rate": 6.9, "risk": "LOW"},
            "SBI Short Duration":   {"nav": round(3189.22 + random.uniform(-2, 2), 2), "rate": 8.1, "risk": "MED"},
            "Axis Corporate Bond":  {"nav": round(2456.89 + random.uniform(-2, 2), 2), "rate": 8.8, "risk": "MED"},
        }

    def project_scale(self, merchants: int, avg_daily_sales: float) -> dict:
        """Scale projections for given merchant count"""
        avg_float_3d = avg_daily_sales * 3
        total_float = merchants * avg_float_3d
        daily = total_float * 0.072 / 365
        return {
            "merchants": merchants,
            "total_float": total_float,
            "daily_yield": daily,
            "monthly_yield": daily * 30,
            "annual_yield": total_float * 0.072,
        }


# ─── Chart Builders ────────────────────────────────────────────────────────────
COLORS = {
    "teal": "#0FB5AE", "blue": "#1A6FBF", "gold": "#F5A623",
    "green": "#27AE60", "red": "#E74C3C", "grey": "#8AAABB",
    "bg": "#132030", "bg2": "#1A2E42",
}

CHART_LAYOUT = dict(
    paper_bgcolor=COLORS["bg"], plot_bgcolor=COLORS["bg"],
    font=dict(color="#FFFFFF", family="Calibri"),
    margin=dict(l=10, r=10, t=35, b=10),
    xaxis=dict(gridcolor="#1E3045", tickfont=dict(color=COLORS["grey"])),
    yaxis=dict(gridcolor="#1E3045", tickfont=dict(color=COLORS["grey"])),
)


def chart_yield_history(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["yield"],
        fill="tozeroy", fillcolor="rgba(15,181,174,0.15)",
        line=dict(color=COLORS["teal"], width=2.5),
        name="Daily Yield (₹)",
        hovertemplate="<b>%{x|%d %b}</b><br>Yield: ₹%{y:.0f}<extra></extra>"
    ))
    fig.update_layout(**CHART_LAYOUT, title=dict(text="30-Day Yield History", font=dict(size=13, color="#FFFFFF")), height=260)
    fig.update_xaxes(showgrid=False)
    return fig


def chart_float_breakdown(state: FloatState) -> go.Figure:
    labels = ["In Settlement", "Invested (Liquid)", "Available Float"]
    values = [state.in_settlement, state.invested_liquid, state.available_float]
    colors = [COLORS["gold"], COLORS["teal"], COLORS["blue"]]
    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.62,
        marker=dict(colors=colors, line=dict(color=COLORS["bg"], width=2)),
        hovertemplate="<b>%{label}</b><br>₹%{value:,.0f}<br>%{percent}<extra></extra>",
        textinfo="none",
    ))
    fig.add_annotation(text=f"₹{state.total_float/100000:.1f}L<br><span style='font-size:11px'>Total</span>",
                       x=0.5, y=0.5, font=dict(size=16, color="#FFFFFF"), showarrow=False)
    fig.update_layout(**{**CHART_LAYOUT, "showlegend": True,
                          "legend": dict(font=dict(color=COLORS["grey"]), bgcolor="rgba(0,0,0,0)"),
                          "title": dict(text="Float Allocation", font=dict(size=13, color="#FFFFFF"))},
                      height=260, margin=dict(l=0, r=0, t=35, b=0))
    return fig


def chart_yield_projection(amount: float, rate: float, days: int) -> go.Figure:
    d = np.arange(0, days+1)
    r_daily = rate / 365
    compound = amount * ((1 + r_daily) ** d - 1)
    simple   = amount * r_daily * d
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=d, y=compound, name="Compound Yield",
        line=dict(color=COLORS["teal"], width=2.5),
        hovertemplate="Day %{x}: ₹%{y:,.0f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=d, y=simple, name="Simple Yield",
        line=dict(color=COLORS["gold"], width=1.5, dash="dash"),
        hovertemplate="Day %{x}: ₹%{y:,.0f}<extra></extra>"))
    fig.update_layout(**CHART_LAYOUT,
                      title=dict(text=f"Yield Projection — ₹{amount:,.0f} at {rate*100:.1f}%", font=dict(size=12, color="#FFFFFF")),
                      height=240, legend=dict(font=dict(color=COLORS["grey"]), bgcolor="rgba(0,0,0,0)"))
    return fig


def chart_scale_projection() -> go.Figure:
    merchant_counts = [1, 5, 10, 50, 100, 500, 1000, 5000, 10000]
    daily_yields = [m * 50000 * 3 * 0.072 / 365 for m in merchant_counts]
    fig = go.Figure(go.Bar(
        x=[str(m) for m in merchant_counts],
        y=daily_yields,
        marker=dict(color=COLORS["teal"], line=dict(color=COLORS["bg"], width=1)),
        hovertemplate="<b>%{x} merchants</b><br>₹%{y:,.0f}/day<extra></extra>",
        text=[f"₹{y:,.0f}" if y < 100000 else f"₹{y/100000:.1f}L" for y in daily_yields],
        textposition="outside", textfont=dict(color=COLORS["teal"], size=9),
    ))
    fig.update_layout(**CHART_LAYOUT,
                      title=dict(text="Daily Yield by Merchant Count (₹50K avg daily sales)", font=dict(size=12, color="#FFFFFF")),
                      height=260, xaxis_title="Merchants", yaxis_title="Daily Yield (₹)")
    return fig


def chart_revenue_5yr() -> go.Figure:
    years = ["Y1\n2026", "Y2\n2027", "Y3\n2028", "Y4\n2029", "Y5\n2030"]
    streams = {
        "Float Yield & Fees": [0.07, 0.7, 2.4, 7, 25],
        "AI Agent Services":  [0.03, 0.3, 1.5, 5, 15],
        "Impact Fund Mgmt":   [0,    0,   0.2, 1,  8],
        "Platform License":   [0,    0,   0.1, 0.5, 3],
    }
    colors_list = [COLORS["teal"], COLORS["blue"], COLORS["green"], COLORS["gold"]]
    fig = go.Figure()
    for (name, vals), color in zip(streams.items(), colors_list):
        fig.add_trace(go.Bar(name=name, x=years, y=vals,
            marker_color=color, hovertemplate=f"{name}<br>₹%{{y:.2f}}Cr<extra></extra>"))
    fig.update_layout(**CHART_LAYOUT, barmode="stack", height=280,
                      title=dict(text="5-Year Revenue Projection (₹ Crore)", font=dict(size=12, color="#FFFFFF")),
                      legend=dict(font=dict(color=COLORS["grey"]), bgcolor="rgba(0,0,0,0)", orientation="h", y=-0.15))
    return fig


# ─── Sidebar ───────────────────────────────────────────────────────────────────
def render_sidebar():
    with st.sidebar:
        st.markdown("""
        <div style='text-align:center; padding:12px 0 4px 0;'>
          <span style='font-size:28px; font-weight:bold; color:#0FB5AE;'>⚡ WORLD OS</span><br>
          <span style='font-size:11px; color:#8AAABB; letter-spacing:2px;'>FLOAT DASHBOARD · POC v1.0</span>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### ⚙️ Configuration")

        merchant = st.selectbox("Active Merchant", ["CCAvenue · Garment Showroom", "Demo Merchant 2", "Demo Merchant 3"])
        auto_refresh = st.toggle("Auto-Refresh (30s)", value=True)
        show_projections = st.toggle("Show Projections", value=True)
        show_agent_log = st.toggle("Show Agent Activity Log", value=True)

        st.markdown("---")
        st.markdown("### 🏦 Investment Settings")
        target_fund = st.selectbox("Preferred Liquid Fund", ["HDFC Liquid (7.5%)", "Nippon Liquid (7.2%)", "Parag Parikh (6.9%)", "SBI Short Duration (8.1%)"])
        auto_invest_threshold = st.number_input("Auto-Invest Threshold (₹)", value=10000, step=5000)

        st.markdown("---")
        st.markdown("### 📊 Scale Simulator")
        sim_merchants = st.slider("Merchant Count", 1, 10000, 50, step=10)
        sim_avg_sales = st.number_input("Avg Daily Sales (₹)", value=50000, step=10000)

        st.markdown("---")
        st.markdown("""
        <div style='font-size:9px; color:#8AAABB; text-align:center; line-height:1.6;'>
          Jagatjyoti Mohanty<br>Roll No. 38/2025 · XLRI CXO Batch 4<br>
          World OS Technologies · 2026<br>
          <span style='color:#E74C3C;'>CONFIDENTIAL</span>
        </div>
        """, unsafe_allow_html=True)

    return {
        "merchant": merchant, "auto_refresh": auto_refresh,
        "show_projections": show_projections, "show_agent_log": show_agent_log,
        "target_fund": target_fund, "auto_invest_threshold": auto_invest_threshold,
        "sim_merchants": sim_merchants, "sim_avg_sales": sim_avg_sales,
    }


# ─── Main Dashboard ────────────────────────────────────────────────────────────
def main():
    engine = FloatEngine()
    config = render_sidebar()

    state = engine.get_state()
    txns  = engine.get_transactions()
    hist  = engine.get_yield_history(30)
    funds = engine.get_fund_prices()

    # ── Header ────────────────────────────────────────────────────────────────
    col_hdr, col_time = st.columns([4, 1])
    with col_hdr:
        st.markdown(f"""
        <div style='display:flex; align-items:center; gap:10px;'>
          <span style='font-size:32px; font-weight:bold; color:#FFFFFF; font-family:Georgia;'>WORLD OS</span>
          <span style='font-size:14px; color:#8AAABB;'> · Float Intelligence Dashboard</span>
          <span><div class='live-dot'></div><span style='color:#27AE60; font-size:12px; font-weight:bold;'>LIVE</span></span>
        </div>
        <div style='font-size:11px; color:#8AAABB; margin-top:2px;'>
          {config["merchant"]}  ·  CCAvenue Gateway  ·  Settlement Rate: 7.2% p.a.
        </div>
        """, unsafe_allow_html=True)
    with col_time:
        st.markdown(f"""
        <div style='text-align:right; margin-top:8px;'>
          <div style='font-size:22px; font-weight:bold; color:#0FB5AE; font-family:Consolas;'>
            {datetime.now().strftime("%H:%M:%S")}
          </div>
          <div style='font-size:10px; color:#8AAABB;'>{datetime.now().strftime("%d %B %Y")}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # ── Top KPI Cards ─────────────────────────────────────────────────────────
    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        st.metric("💰 TOTAL FLOAT", f"₹{state.total_float/100000:.1f}L", delta="Calculating...")
    with k2:
        st.metric("📈 YIELD TODAY", f"₹{state.daily_yield:.0f}", delta=f"7.2% p.a.")
    with k3:
        st.metric("💤 IDLE CASH", f"₹{state.idle_cash/100000:.1f}L", delta=f"-₹{state.idle_cash*0.072/365:.0f}/day lost", delta_color="inverse")
    with k4:
        st.metric("🚀 30-DAY PROJ", f"₹{state.projection_30d:,.0f}", delta="Compound growth")
    with k5:
        invested = state.invested_liquid / state.in_bank * 100
        st.metric("⚡ DEPLOYED %", f"{invested:.0f}%", delta="of bank balance")

    st.markdown("")

    # ── Row 1: Settlement Countdown + Float Allocation ─────────────────────────
    col_left, col_right = st.columns([1.1, 0.9])

    with col_left:
        st.markdown('<div class="section-header">⏱ Settlement Countdown</div>', unsafe_allow_html=True)
        for txn in txns:
            hrs = txn.hours_remaining
            if hrs < 12:
                bar_color, badge_class, label = "#E74C3C", "badge-red", "TODAY"
            elif hrs < 36:
                bar_color, badge_class, label = "#F5A623", "badge-gold", "TOMORROW"
            else:
                bar_color, badge_class, label = "#27AE60", "badge-green", "DAY AFTER"

            prog_pct = int(txn.progress * 100)
            st.markdown(f"""
            <div class='txn-row' style='border-color:{bar_color};'>
              <div style='display:flex; justify-content:space-between; align-items:center;'>
                <div>
                  <span style='color:#8AAABB; font-size:11px;'>{txn.txn_id}</span>
                  <span class='badge {badge_class}'>{label}</span>
                </div>
                <span style='color:{bar_color}; font-weight:bold; font-size:16px;'>₹{txn.amount:,.0f}</span>
              </div>
              <div style='font-size:10px; color:#8AAABB; margin:4px 0;'>{hrs:.0f}h remaining until settlement</div>
              <div style='background:#1E3045; height:6px; border-radius:3px; margin-top:4px;'>
                <div style='background:{bar_color}; width:{prog_pct}%; height:6px; border-radius:3px;'></div>
              </div>
            </div>
            """, unsafe_allow_html=True)

        total_pending = sum(t.amount for t in txns)
        st.markdown(f"""
        <div style='background:#1A2E42; border-radius:6px; padding:10px 14px; margin-top:8px;
                    display:flex; justify-content:space-between;'>
          <span style='color:#8AAABB; font-size:11px;'>Total in Settlement Pipeline</span>
          <span style='color:#0FB5AE; font-weight:bold;'>₹{total_pending:,.0f}</span>
        </div>
        """, unsafe_allow_html=True)

    with col_right:
        st.markdown('<div class="section-header">🥧 Float Allocation</div>', unsafe_allow_html=True)
        st.plotly_chart(chart_float_breakdown(state), use_container_width=True)

        # Idle cash opportunity
        daily_idle_loss = state.idle_cash * 0.072 / 365
        st.markdown(f"""
        <div style='background:#1A2E42; border:1px solid #F5A623; border-radius:8px; padding:12px; margin-top:4px;'>
          <div style='color:#F5A623; font-weight:bold; font-size:11px; letter-spacing:2px;'>💡 IDLE CASH OPPORTUNITY</div>
          <div style='margin-top:8px; display:flex; justify-content:space-between;'>
            <span style='color:#8AAABB; font-size:12px;'>Idle Amount</span>
            <span style='color:#E74C3C; font-weight:bold;'>₹{state.idle_cash:,.0f}</span>
          </div>
          <div style='display:flex; justify-content:space-between;'>
            <span style='color:#8AAABB; font-size:12px;'>Daily Cost of Inaction</span>
            <span style='color:#E74C3C; font-weight:bold;'>-₹{daily_idle_loss:.0f}/day</span>
          </div>
          <div style='display:flex; justify-content:space-between;'>
            <span style='color:#8AAABB; font-size:12px;'>If Invested @ 7.2%</span>
            <span style='color:#27AE60; font-weight:bold;'>+₹{daily_idle_loss:.0f}/day</span>
          </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("")

    # ── Row 2: Yield History + Yield Calculator ────────────────────────────────
    col_hist, col_calc = st.columns([1.4, 0.6])
    with col_hist:
        st.markdown('<div class="section-header">📈 30-Day Yield History</div>', unsafe_allow_html=True)
        st.plotly_chart(chart_yield_history(hist), use_container_width=True)

    with col_calc:
        st.markdown('<div class="section-header">🧮 Yield Calculator</div>', unsafe_allow_html=True)
        calc_amount = st.number_input("Investment Amount (₹)", value=100000, step=10000, key="calc_amt")
        calc_rate   = st.slider("Annual Rate (%)", 5.0, 10.0, 7.2, step=0.1, key="calc_rate") / 100
        calc_days   = st.slider("Duration (Days)", 1, 365, 30, key="calc_days")
        r_daily = calc_rate / 365
        calc_yield_total = calc_amount * ((1 + r_daily) ** calc_days - 1)
        calc_yield_daily = calc_amount * r_daily

        c1, c2 = st.columns(2)
        c1.metric("Daily Yield", f"₹{calc_yield_daily:.0f}")
        c2.metric("Total Earned", f"₹{calc_yield_total:,.0f}")
        st.plotly_chart(chart_yield_projection(calc_amount, calc_rate, calc_days), use_container_width=True)

    # ── Row 3: Recommended Funds ───────────────────────────────────────────────
    st.markdown('<div class="section-header">🏦 Recommended Liquid Funds  (Live NAV)</div>', unsafe_allow_html=True)
    fcols = st.columns(len(funds))
    for (fname, fdata), col in zip(funds.items(), fcols):
        risk_class = "badge-green" if fdata["risk"] == "LOW" else "badge-gold"
        with col:
            st.markdown(f"""
            <div style='background:#132030; border:1px solid #1A2E42; border-top:3px solid
                {"#27AE60" if fdata["risk"]=="LOW" else "#F5A623"};
                border-radius:8px; padding:12px; text-align:center;'>
              <div style='font-size:10px; color:#8AAABB; margin-bottom:6px;'>{fname}</div>
              <div style='font-size:22px; font-weight:bold; color:{"#27AE60" if fdata["risk"]=="LOW" else "#F5A623"};'>
                {fdata["rate"]}%
              </div>
              <div style='font-size:10px; color:#8AAABB;'>NAV: ₹{fdata["nav"]:.2f}</div>
              <span class='badge {risk_class}'>{fdata["risk"]} RISK</span>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("")

    # ── Row 4: Scale Simulator + Revenue Projection ───────────────────────────
    if config["show_projections"]:
        st.markdown('<div class="section-header">🔭 Scale Projections</div>', unsafe_allow_html=True)
        col_scale, col_rev = st.columns([1, 1])

        with col_scale:
            proj = engine.project_scale(config["sim_merchants"], config["sim_avg_sales"])
            st.markdown(f"""
            <div style='background:#132030; border:1px solid #0FB5AE; border-radius:10px; padding:16px; margin-bottom:10px;'>
              <div style='color:#0FB5AE; font-size:11px; font-weight:bold; letter-spacing:2px;'>SCALE SIMULATION</div>
              <div style='margin-top:12px; display:grid; grid-template-columns:1fr 1fr; gap:8px;'>
                <div><div style='color:#8AAABB;font-size:10px;'>Merchants</div>
                     <div style='color:#FFFFFF;font-weight:bold;font-size:18px;'>{proj["merchants"]:,}</div></div>
                <div><div style='color:#8AAABB;font-size:10px;'>Total Float</div>
                     <div style='color:#0FB5AE;font-weight:bold;font-size:18px;'>₹{proj["total_float"]/100000:.1f}L</div></div>
                <div><div style='color:#8AAABB;font-size:10px;'>Daily Yield</div>
                     <div style='color:#F5A623;font-weight:bold;font-size:18px;'>₹{proj["daily_yield"]:,.0f}</div></div>
                <div><div style='color:#8AAABB;font-size:10px;'>Annual Yield</div>
                     <div style='color:#27AE60;font-weight:bold;font-size:18px;'>₹{proj["annual_yield"]/100000:.1f}L</div></div>
              </div>
            </div>
            """, unsafe_allow_html=True)
            st.plotly_chart(chart_scale_projection(), use_container_width=True)

        with col_rev:
            st.plotly_chart(chart_revenue_5yr(), use_container_width=True)

    # ── Agent Activity Log ────────────────────────────────────────────────────
    if config["show_agent_log"]:
        st.markdown('<div class="section-header">🤖 Agent Activity Log</div>', unsafe_allow_html=True)
        log_entries = [
            (datetime.now() - timedelta(minutes=2),  "Agent 1", "Float updated — Daily sales: ₹50,000 · Total float: ₹4.0L",                   "green"),
            (datetime.now() - timedelta(minutes=5),  "System",  "Dashboard initialized — CCAvenue POC mode active",                               "blue"),
            (datetime.now() - timedelta(minutes=8),  "Agent 1", "Float mechanism connected to garment showroom account",                           "teal"),
            (datetime.now() - timedelta(minutes=12), "Agent 2", "Weekly problem scan complete — 5 solvable local problems identified",              "gold"),
            (datetime.now() - timedelta(minutes=18), "System",  "World OS Engine v1.0 loaded — ready for POC",                                     "blue"),
            (datetime.now() - timedelta(hours=1),    "Agent 1", "TXN-8363 created: ₹20,000 settlement initiated via CCAvenue",                     "teal"),
            (datetime.now() - timedelta(hours=2),    "Agent 2", "Problem Report #1 generated: Food waste mapping in Hyderabad markets",            "gold"),
            (datetime.now() - timedelta(hours=6),    "System",  "Liquid fund NAV sync complete — HDFC 7.5%, Nippon 7.2%, Parag Parikh 6.9%",      "blue"),
        ]
        log_df = pd.DataFrame([
            {"Time": t.strftime("%H:%M:%S"), "Agent": ag, "Message": msg, "_color": col}
            for t, ag, msg, col in log_entries
        ])
        for _, row in log_df.iterrows():
            color_map = {"green": "#27AE60", "blue": "#1A6FBF", "teal": "#0FB5AE", "gold": "#F5A623"}
            c = color_map.get(row["_color"], "#8AAABB")
            st.markdown(f"""
            <div style='background:#1A2E42; border-radius:6px; padding:8px 12px; margin:3px 0;
                        border-left:3px solid {c}; font-size:11px;'>
              <span style='color:#8AAABB;'>{row["Time"]}</span>
              <span class='badge' style='background:rgba(0,0,0,0.3); color:{c}; margin:0 8px;'>{row["Agent"]}</span>
              <span style='color:#CCCCCC;'>{row["Message"]}</span>
            </div>
            """, unsafe_allow_html=True)

    # ── Footer ────────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("""
    <div style='text-align:center; color:#8AAABB; font-size:10px; padding:8px 0;'>
      ⚡ WORLD OS  ·  Float Intelligence Dashboard  ·  POC v1.0
      ·  Jagatjyoti Mohanty  ·  Roll No. 38/2025  ·  XLRI CXO Batch 4  ·  2026
      &nbsp;&nbsp;|&nbsp;&nbsp;
      <span style='color:#E74C3C;'>CONFIDENTIAL</span>
      &nbsp;·&nbsp;
      <span style='color:#27AE60;'>● LIVE</span>
    </div>
    """, unsafe_allow_html=True)

    # Auto-refresh
    if config["auto_refresh"]:
        time.sleep(0.1)
        st.rerun()


if __name__ == "__main__":
    main()
