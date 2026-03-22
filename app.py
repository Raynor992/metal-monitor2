import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# 基础配置
st.set_page_config(page_title="全球宏观监控", layout="wide")

# ===================== 极简工具函数 =====================
def get_last(series):
    return float(series.iloc[-1]) if not series.empty else 0.0

def get_pct(series):
    if len(series) < 2:
        return 0.0
    p = float(series.iloc[-2])
    c = float(series.iloc[-1])
    return round(((c - p) / p) * 100, 2) if p != 0 else 0.0

# ===================== 极简数据加载 =====================
@st.cache_data(ttl=300)
def load():
    data = {}
    # 美股
    try:
        data['nas'] = yf.download("^IXIC", period="30d", progress=False)["Close"]
        data['sp500'] = yf.download("^GSPC", period="30d", progress=False)["Close"]
    except:
        data['nas'] = data['sp500'] = pd.Series([0]*30)
    
    # 大宗商品
    try:
        data['gold'] = yf.download("GC=F", period="30d", progress=False)["Close"]
        data['oil'] = yf.download("CL=F", period="30d", progress=False)["Close"]
    except:
        data['gold'] = data['oil'] = pd.Series([0]*30)
    
    # 美元
    try:
        data['dxy'] = yf.download("DX-Y.NYB", period="30d", progress=False)["Close"]
    except:
        data['dxy'] = pd.Series([0]*30)
    
    return data

d = load()

# ===================== 极简侧边栏 =====================
page = st.sidebar.radio("选择", ["全球股票", "大宗商品", "美元"])
if st.sidebar.button("刷新"):
    st.cache_data.clear()
    st.rerun()

# ===================== 极简页面逻辑 =====================
if page == "全球股票":
    st.title("🌍 全球股票")
    c1, c2 = st.columns(2)
    with c1:
        v, p = get_last(d['nas']), get_pct(d['nas'])
        st.metric("纳指", f"{v:.2f}", f"{p:.2f}%", delta_color="inverse")
    with c2:
        v, p = get_last(d['sp500']), get_pct(d['sp500'])
        st.metric("标普500", f"{v:.2f}", f"{p:.2f}%", delta_color="inverse")
    
    st.subheader("走势")
    fig = go.Figure()
    fig.add_trace(go.Scatter(y=d['nas'], name="纳指", line=dict(color="#e63946")))
    fig.add_trace(go.Scatter(y=d['sp500'], name="标普500", line=dict(color="#2a9d8f")))
    st.plotly_chart(fig, use_container_width=True)

elif page == "大宗商品":
    st.title("🛢️ 大宗商品")
    c1, c2 = st.columns(2)
    with c1:
        v, p = get_last(d['gold']), get_pct(d['gold'])
        st.metric("黄金", f"{v:.2f}", f"{p:.2f}%", delta_color="inverse")
    with c2:
        v, p = get_last(d['oil']), get_pct(d['oil'])
        st.metric("原油", f"{v:.2f}", f"{p:.2f}%", delta_color="inverse")
    
    st.subheader("走势")
    fig = go.Figure()
    fig.add_trace(go.Scatter(y=d['gold'], name="黄金", line=dict(color="#f59e0b")))
    fig.add_trace(go.Scatter(y=d['oil'], name="原油", line=dict(color="#ef4444")))
    st.plotly_chart(fig, use_container_width=True)

elif page == "美元":
    st.title("💵 美元指数")
    v, p = get_last(d['dxy']), get_pct(d['dxy'])
    st.metric("美元指数(DXY)", f"{v:.2f}", f"{p:.2f}%", delta_color="inverse")
    
    st.subheader("走势")
    fig = go.Figure()
    fig.add_trace(go.Scatter(y=d['dxy'], name="美元指数", line=dict(color="#1d4ed8")))
    st.plotly_chart(fig, use_container_width=True)
