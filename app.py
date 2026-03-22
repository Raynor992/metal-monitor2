import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from fredapi import Fred
import warnings

warnings.filterwarnings('ignore')
st.set_page_config(page_title="全球宏观监控系统", layout="wide", initial_sidebar_state="expanded", page_icon="📊")

# 样式：涨红跌绿 + 卡片美化
st.markdown("""
<style>
div[data-testid="metric-container"] {background:#f8f9fa; padding:12px; border-radius:10px; margin-bottom:8px;}
</style>
""", unsafe_allow_html=True)

# ===================== 密钥配置 =====================
FRED_API_KEY = "cc31d1914c0dd0e60a7f384aefdeec52"
fred = None
if FRED_API_KEY:
    try:
        fred = Fred(api_key=FRED_API_KEY)
    except:
        fred = None

# ===================== 工具函数 =====================
def safe_val(series):
    if series.empty:
        return 0.0
    last_val = series.iloc[-1]
    return float(last_val) if pd.notna(last_val) else 0.0

def safe_pct(series):
    if len(series) < 2:
        return 0.0
    prev = series.iloc[-2]
    curr = series.iloc[-1]
    if pd.isna(prev) or pd.isna(curr) or prev == 0:
        return 0.0
    return round(((curr - prev) / prev) * 100, 2)

def big_hover(fig):
    fig.update_layout(
        hoverlabel=dict(font_size=18, font_weight="bold", bgcolor="#f1f3f5"),
        hovertemplate="<b>时间：%{x}</b><br>数值：%{y}<extra></extra>",
        template="simple_white"
    )
    return fig

# ===================== 数据加载 =====================
@st.cache_data(ttl=300, show_spinner="正在加载数据...")
def load_data():
    data = {}
    # 美股数据
    for name, code in {"纳指":"^IXIC", "标普500":"^GSPC", "道指":"^DJI"}.items():
        try:
            df = yf.download(code, period="30d", progress=False)
            data[f"us_{name}"] = df["Close"].dropna() if not df.empty else pd.Series([0.0]*30)
        except:
            data[f"us_{name}"] = pd.Series([0.0]*30)

    # 大宗商品数据
    for name, code in {"黄金":"GC=F", "白银":"SI=F", "铜":"HG=F", "原油":"CL=F", "天然气":"NG=F"}.items():
        try:
            df = yf.download(code, period="30d", progress=False)
            data[f"comm_{name}"] = df["Close"].dropna() if not df.empty else pd.Series([0.0]*30)
        except:
            data[f"comm_{name}"] = pd.Series([0.0]*30)

    # 美元美债数据
    try:
        df_dxy = yf.download("DX-Y.NYB", period="30d", progress=False)
        data["dxy"] = df_dxy["Close"].dropna() if not df_dxy.empty else pd.Series([0.0]*30)
    except:
        data["dxy"] = pd.Series([0.0]*30)
    
    try:
        data["bond10"] = fred.get_series('DGS10').dropna().tail(30) if fred else pd.Series([0.0]*30)
    except:
        data["bond10"] = pd.Series([0.0]*30)
    
    try:
        data["real10"] = fred.get_series('DFII10').dropna().tail(30) if fred else pd.Series([0.0]*30)
    except:
        data["real10"] = pd.Series([0.0]*30)
    
    return data

d = load_data()

# ===================== 侧边栏 =====================
st.sidebar.title("📋 宏观监控导航")
page = st.sidebar.radio("选择板块", ["全球股票", "大宗商品", "美元美债"])
if st.sidebar.button("🔄 立即刷新"):
    st.cache_data.clear()
    try:
        st.rerun()
    except:
        st.experimental_rerun()

# ===================== 板块逻辑 =====================
if page == "全球股票":
    st.title("🌍 全球股票指数")
    col1,col2,col3 = st.columns(3)
    with col1: 
        v, p = safe_val(d['us_纳指']), safe_pct(d['us_纳指'])
        st.metric("纳指", f"{v:.2f}", f"{p:.2f}%", delta_color="inverse")
    with col2: 
        v, p = safe_val(d['us_标普500']), safe_pct(d['us_标普500'])
        st.metric("标普500", f"{v:.2f}", f"{p:.2f}%", delta_color="inverse")
    with col3: 
        v, p = safe_val(d['us_道指']), safe_pct(d['us_道指'])
        st.metric("道指", f"{v:.2f}", f"{p:.2f}%", delta_color="inverse")
    
    st.subheader("📈 美股走势")
    fig = go.Figure()
    fig.add_trace(go.Scatter(y=d["us_纳指"], name="纳指", line=dict(color="#e63946", width=2)))
    fig.add_trace(go.Scatter(y=d["us_标普500"], name="标普500", line=dict(color="#2a9d8f", width=2)))
    st.plotly_chart(big_hover(fig), use_container_width=True)

elif page == "大宗商品":
    st.title("🛢️ 大宗商品期货")
    col1,col2,col3,col4,col5 = st.columns(5)
    commodities = ["黄金","白银","铜","原油","天然气"]
    cols = [col1,col2,col3,col4,col5]
    for idx, name in enumerate(commodities):
        with cols[idx]:
            v, p = safe_val(d[f"comm_{name}"]), safe_pct(d[f"comm_{name}"])
            st.metric(name, f"{v:.2f}", f"{p:.2f}%", delta_color="inverse")
    
    st.subheader("📈 黄金/原油走势")
    fig = go.Figure()
    fig.add_trace(go.Scatter(y=d["comm_黄金"], name="黄金", line=dict(color="#f59e0b", width=2)))
    fig.add_trace(go.Scatter(y=d["comm_原油"], name="原油", line=dict(color="#ef4444", width=2)))
    st.plotly_chart(big_hover(fig), use_container_width=True)

elif page == "美元美债":
    st.title("💵 美元&美债指数")
    col1,col2,col3 = st.columns(3)
    with col1:
        v, p = safe_val(d["dxy"]), safe_pct(d["dxy"])
        st.metric("美元指数(DXY)", f"{v:.2f}", f"{p:.2f}%", delta_color="inverse")
    with col2: 
        v, p = safe_val(d["bond10"]), safe_pct(d["bond10"])
        st.metric("10年期收益率", f"{v:.2f}%", f"{p:.2f}%", delta_color="inverse")
    with col3: 
        v, p = safe_val(d["real10"]), safe_pct(d["real10"])
        st.metric("10年期实际利率", f"{v:.2f}%", f"{p:.2f}%", delta_color="inverse")
    
    st.subheader("📈 美元指数走势")
    fig = go.Figure()
    fig.add_trace(go.Scatter(y=d["dxy"], name="美元指数", line=dict(color="#1d4ed8", width=2)))
    st.plotly_chart(big_hover(fig), use_container_width=True)

st.markdown("---")
st.caption("数据来源：Yahoo Finance / FRED")
