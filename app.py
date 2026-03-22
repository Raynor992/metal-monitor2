import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from fredapi import Fred
import warnings

# 基础配置
warnings.filterwarnings('ignore')
st.set_page_config(
    page_title="全球宏观监控系统",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="📊"
)

# 全局样式
st.markdown("""
<style>
.metric-card {
    background: #f8fafc;
    border-radius: 12px;
    padding: 18px;
    border: 1px solid #e2e8f0;
    margin-bottom: 12px;
}
.metric-value {
    font-size: 28px;
    font-weight: 800;
    color: #0f172a;
    margin: 8px 0;
}
.metric-up {
    color: #e63946;
    font-weight: 700;
    font-size: 16px;
}
.metric-down {
    color: #22c55e;
    font-weight: 700;
    font-size: 16px;
}
.metric-flat {
    color: #64748b;
    font-size: 16px;
}
.module-title {
    font-size: 22px;
    font-weight: 700;
    color: #0f172a;
    margin: 24px 0 16px 0;
}
.block-container {
    padding-top: 2rem;
    padding-left: 3rem;
    padding-right: 3rem;
}
</style>
""", unsafe_allow_html=True)

# ===================== 密钥配置 =====================
FRED_API_KEY = "cc31d1914c0dd0e60a7f384aefdeec52"
fred = None
if FRED_API_KEY and FRED_API_KEY != "你的FRED密钥":
    try:
        fred = Fred(api_key=FRED_API_KEY)
        st.sidebar.success("✅ FRED API连接成功")
    except Exception as e:
        st.sidebar.error(f"❌ FRED API连接失败：{str(e)}")
        fred = None

# ===================== 稳定工具函数 =====================
def get_latest_value(series):
    if series.empty:
        return 0.0
    latest = series.iloc[-1]
    return float(latest) if pd.notna(latest) else 0.0

def get_change_pct(series):
    if len(series) < 2:
        return 0.0
    prev = float(series.iloc[-2])
    curr = float(series.iloc[-1])
    if pd.isna(prev) or pd.isna(curr) or prev == 0:
        return 0.0
    return round(((curr - prev) / prev) * 100, 2)

def get_change_color(pct):
    if pct > 0:
        return "metric-up"
    elif pct < 0:
        return "metric-down"
    else:
        return "metric-flat"

def config_chart(fig):
    fig.update_layout(
        hoverlabel=dict(font_size=18, font_weight="bold", bgcolor="#f8fafc", bordercolor="#e2e8f0", padding=10),
        hovertemplate="<b>时间：%{x}</b><br>数值：<span style='font-size:20px; font-weight:800'>%{y}</span><extra></extra>",
        template="plotly_white",
        height=450,
        margin=dict(l=20, r=20, t=40, b=20)
    )
    return fig

# ===================== 云端稳定数据加载（全yfinance） =====================
@st.cache_data(ttl=300, show_spinner="正在加载全球市场数据...")
def load_data():
    data = {}
    error_log = []

    # -------------------- 1. A股指数（yfinance原生支持，稳定） --------------------
    a_stocks = {
        "上证指数": "000001.SS",
        "深证成指": "399001.SZ",
        "创业板指": "399006.SZ",
        "沪深300": "000300.SS"
    }
    for name, code in a_stocks.items():
        try:
            df = yf.download(code, period="30d", progress=False, show_errors=False, auto_adjust=False)
            if not df.empty:
                data[f"a_{name}"] = df["Close"].dropna()
            else:
                data[f"a_{name}"] = pd.Series([0.0]*30)
                error_log.append(f"A股{name}数据加载失败")
        except Exception as e:
            data[f"a_{name}"] = pd.Series([0.0]*30)
            error_log.append(f"A股{name}加载错误：{str(e)}")

    # -------------------- 2. 美股指数 --------------------
    us_stocks = {
        "道琼斯指数": "^DJI",
        "纳斯达克综指": "^IXIC",
        "标普500": "^GSPC",
        "纳斯达克100": "^NDX"
    }
    for name, code in us_stocks.items():
        try:
            df = yf.download(code, period="30d", progress=False, show_errors=False, auto_adjust=False)
            if not df.empty:
                data[f"us_{name}"] = df["Close"].dropna()
            else:
                data[f"us_{name}"] = pd.Series([0.0]*30)
                error_log.append(f"美股{name}数据加载失败")
        except Exception as e:
            data[f"us_{name}"] = pd.Series([0.0]*30)
            error_log.append(f"美股{name}加载错误：{str(e)}")

    # -------------------- 3. 大宗商品 --------------------
    commodities = {
        "黄金": "GC=F", "白银": "SI=F", "铜": "HG=F",
        "铝": "ALI=F", "WTI原油": "CL=F", "布伦特原油": "BZ=F", "天然气": "NG=F"
    }
    for name, code in commodities.items():
        try:
            df = yf.download(code, period="30d", progress=False, show_errors=False, auto_adjust=False)
            if not df.empty:
                data[f"comm_{name}"] = df["Close"].dropna()
            else:
                data[f"comm_{name}"] = pd.Series([0.0]*30)
                error_log.append(f"大宗商品{name}数据加载失败")
        except Exception as e:
            data[f"comm_{name}"] = pd.Series([0.0]*30)
            error_log.append(f"大宗商品{name}加载错误：{str(e)}")

    # -------------------- 4. 美元&美债 --------------------
    # 美元指数
    try:
        dxy_df = yf.download("DX-Y.NYB", period="30d", progress=False, show_errors=False, auto_adjust=False)
        if not dxy_df.empty:
            data["dxy"] = dxy_df["Close"].dropna()
        else:
            data["dxy"] = pd.Series([0.0]*30)
            error_log.append("美元指数数据加载失败")
    except Exception as e:
        data["dxy"] = pd.Series([0.0]*30)
        error_log.append(f"美元指数加载错误：{str(e)}")

    # 美元兑人民币
    try:
        cny_df = yf.download("CNY=X", period="30d", progress=False, show_errors=False, auto_adjust=False)
        if not cny_df.empty:
            data["usd_cny"] = cny_df["Close"].dropna()
        else:
            data["usd_cny"] = pd.Series([0.0]*30)
            error_log.append("美元兑人民币数据加载失败")
    except Exception as e:
        data["usd_cny"] = pd.Series([0.0]*30)
        error_log.append(f"美元兑人民币加载错误：{str(e)}")

    # 美债数据
    bond_series = {
        "2年期美债收益率": "DGS2",
        "10年期美债收益率": "DGS10",
        "30年期美债收益率": "DGS30",
        "10年期实际利率": "DFII10"
    }
    for name, code in bond_series.items():
        try:
            if fred:
                series = fred.get_series(code).dropna().tail(30)
                if not series.empty:
                    data[f"bond_{name}"] = series
                else:
                    data[f"bond_{name}"] = pd.Series([0.0]*30)
                    error_log.append(f"{name}数据加载失败")
            else:
                data[f"bond_{name}"] = pd.Series([0.0]*30)
        except Exception as e:
            data[f"bond_{name}"] = pd.Series([0.0]*30)
            error_log.append(f"{name}加载错误：{str(e)}")

    return data, error_log

# 加载数据
with st.spinner("正在加载全球市场数据..."):
    market_data, load_errors = load_data()

# 显示加载错误（方便排查问题）
if load_errors:
    with st.expander("⚠️ 数据加载异常详情", expanded=False):
        for err in load_errors:
            st.write(err)

# ===================== 侧边栏 =====================
st.sidebar.title("📊 全球宏观监控")
selected_page = st.sidebar.radio(
    "选择监控板块",
    ["📈 全球股票指数", "🛢️ 大宗商品期货", "💵 美元&美债市场"],
    index=0
)
st.sidebar.divider()
if st.sidebar.button("🔄 刷新全部数据", type="primary", use_container_width=True):
    st.cache_data.clear()
    try:
        st.rerun()
    except:
        st.experimental_rerun()
st.sidebar.caption("数据每5分钟自动刷新")

# ===================== 页面渲染 =====================
if selected_page == "📈 全球股票指数":
    st.title("📈 全球股票核心指数")
    st.divider()

    # A股
    st.markdown("<div class='module-title'>🇨🇳 A股核心指数</div>", unsafe_allow_html=True)
    a_cols = st.columns(4)
    a_list = ["上证指数", "深证成指", "创业板指", "沪深300"]
    for idx, name in enumerate(a_list):
        with a_cols[idx]:
            s = market_data[f"a_{name}"]
            val = get_latest_value(s)
            pct = get_change_pct(s)
            color = get_change_color(pct)
            st.markdown(f"""
            <div class='metric-card'>
                <div style='font-size:16px; color:#475569; font-weight:600;'>{name}</div>
                <div class='metric-value'>{val:.2f}</div>
                <div class='{color}'>{pct:.2f}%</div>
            </div>
            """, unsafe_allow_html=True)

    # 美股
    st.markdown("<div class='module-title'>🇺🇸 美股核心指数</div>", unsafe_allow_html=True)
    us_cols = st.columns(4)
    us_list = ["道琼斯指数", "纳斯达克综指", "标普500", "纳斯达克100"]
    for idx, name in enumerate(us_list):
        with us_cols[idx]:
            s = market_data[f"us_{name}"]
            val = get_latest_value(s)
            pct = get_change_pct(s)
            color = get_change_color(pct)
            st.markdown(f"""
            <div class='metric-card'>
                <div style='font-size:16px; color:#475569; font-weight:600;'>{name}</div>
                <div class='metric-value'>{val:.2f}</div>
                <div class='{color}'>{pct:.2f}%</div>
            </div>
            """, unsafe_allow_html=True)

    # 图表
    st.markdown("<div class='module-title'>📈 美股指数30日走势</div>", unsafe_allow_html=True)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=market_data["us_纳斯达克综指"].index, y=market_data["us_纳斯达克综指"].values, name="纳斯达克综指", line=dict(color="#e63946", width=2.5)))
    fig.add_trace(go.Scatter(x=market_data["us_标普500"].index, y=market_data["us_标普500"].values, name="标普500", line=dict(color="#22c55e", width=2.5)))
    fig.add_trace(go.Scatter(x=market_data["us_道琼斯指数"].index, y=market_data["us_道琼斯指数"].values, name="道琼斯指数", line=dict(color="#3b82f6", width=2.5)))
    fig.update_layout(title="纳斯达克综指 vs 标普500 vs 道琼斯指数", xaxis_title="日期", yaxis_title="指数点数")
    st.plotly_chart(config_chart(fig), use_container_width=True)

elif selected_page == "🛢️ 大宗商品期货":
    st.title("🛢️ 大宗商品期货监控")
    st.divider()

    # 贵金属
    st.markdown("<div class='module-title'>🥇 贵金属</div>", unsafe_allow_html=True)
    metal_cols = st.columns(2)
    for idx, name in enumerate(["黄金", "白银"]):
        with metal_cols[idx]:
            s = market_data[f"comm_{name}"]
            val = get_latest_value(s)
            pct = get_change_pct(s)
            color = get_change_color(pct)
            st.markdown(f"""
            <div class='metric-card'>
                <div style='font-size:16px; color:#475569; font-weight:600;'>{name}</div>
                <div class='metric-value'>{val:.2f}</div>
                <div style='font-size:14px; color:#64748b; margin-bottom:8px;'>USD/盎司</div>
                <div class='{color}'>{pct:.2f}%</div>
            </div>
            """, unsafe_allow_html=True)

    # 工业金属
    st.markdown("<div class='module-title'>⚙️ 工业金属</div>", unsafe_allow_html=True)
    industry_cols = st.columns(3)
    for idx, name in enumerate(["铜", "铝"]):
        with industry_cols[idx]:
            s = market_data[f"comm_{name}"]
            val = get_latest_value(s)
            pct = get_change_pct(s)
            color = get_change_color(pct)
            st.markdown(f"""
            <div class='metric-card'>
                <div style='font-size:16px; color:#475569; font-weight:600;'>{name}</div>
                <div class='metric-value'>{val:.2f}</div>
                <div style='font-size:14px; color:#64748b; margin-bottom:8px;'>USD/吨</div>
                <div class='{color}'>{pct:.2f}%</div>
            </div>
            """, unsafe_allow_html=True)

    # 能源
    st.markdown("<div class='module-title'>⛽ 能源商品</div>", unsafe_allow_html=True)
    energy_cols = st.columns(3)
    for idx, name in enumerate(["WTI原油", "布伦特原油", "天然气"]):
        with energy_cols[idx]:
            s = market_data[f"comm_{name}"]
            val = get_latest_value(s)
            pct = get_change_pct(s)
            color = get_change_color(pct)
            unit = "USD/桶" if "原油" in name else "USD/MMBtu"
            st.markdown(f"""
            <div class='metric-card'>
                <div style='font-size:16px; color:#475569; font-weight:600;'>{name}</div>
                <div class='metric-value'>{val:.2f}</div>
                <div style='font-size:14px; color:#64748b; margin-bottom:8px;'>{unit}</div>
                <div class='{color}'>{pct:.2f}%</div>
            </div>
            """, unsafe_allow_html=True)

    # 图表
    st.markdown("<div class='module-title'>📈 黄金&原油30日走势</div>", unsafe_allow_html=True)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=market_data["comm_黄金"].index, y=market_data["comm_黄金"].values, name="黄金", line=dict(color="#f59e0b", width=2.5)))
    fig.add_trace(go.Scatter(x=market_data["comm_WTI原油"].index, y=market_data["comm_WTI原油"].values, name="WTI原油", line=dict(color="#ef4444", width=2.5), yaxis="y2"))
    fig.update_layout(
        title="黄金 vs WTI原油走势",
        xaxis_title="日期",
        yaxis=dict(title="黄金价格(USD/盎司)", side="left"),
        yaxis2=dict(title="原油价格(USD/桶)", side="right", overlaying="y"),
        legend=dict(x=0.01, y=0.99)
    )
    st.plotly_chart(config_chart(fig), use_container_width=True)

elif selected_page == "💵 美元&美债市场":
    st.title("💵 美元&美债市场监控")
    st.divider()

    # 美元汇率
    st.markdown("<div class='module-title'>💵 美元汇率</div>", unsafe_allow_html=True)
    usd_cols = st.columns(2)
    for idx, (name, key) in enumerate([("美元指数(DXY)", "dxy"), ("美元兑人民币", "usd_cny")]):
        with usd_cols[idx]:
            s = market_data[key]
            val = get_latest_value(s)
            pct = get_change_pct(s)
            color = get_change_color(pct)
            st.markdown(f"""
            <div class='metric-card'>
                <div style='font-size:16px; color:#475569; font-weight:600;'>{name}</div>
                <div class='metric-value'>{val:.4f}</div>
                <div class='{color}'>{pct:.2f}%</div>
            </div>
            """, unsafe_allow_html=True)

    # 美债收益率
    st.markdown("<div class='module-title'>📜 美债收益率</div>", unsafe_allow_html=True)
    bond_cols = st.columns(4)
    bond_list = ["2年期美债收益率", "10年期美债收益率", "30年期美债收益率", "10年期实际利率"]
    for idx, name in enumerate(bond_list):
        with bond_cols[idx]:
            s = market_data[f"bond_{name}"]
            val = get_latest_value(s)
            pct = get_change_pct(s)
            color = get_change_color(pct)
            st.markdown(f"""
            <div class='metric-card'>
                <div style='font-size:16px; color:#475569; font-weight:600;'>{name}</div>
                <div class='metric-value'>{val:.2f}%</div>
                <div class='{color}'>{pct:.2f}%</div>
            </div>
            """, unsafe_allow_html=True)

    # 图表
    st.markdown("<div class='module-title'>📈 美元指数&10年期美债收益率30日走势</div>", unsafe_allow_html=True)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=market_data["dxy"].index, y=market_data["dxy"].values, name="美元指数", line=dict(color="#1e40af", width=2.5)))
    fig.add_trace(go.Scatter(x=market_data["bond_10年期美债收益率"].index, y=market_data["bond_10年期美债收益率"].values, name="10年期美债收益率", line=dict(color="#dc2626", width=2.5), yaxis="y2"))
    fig.update_layout(
        title="美元指数 vs 10年期美债收益率",
        xaxis_title="日期",
        yaxis=dict(title="美元指数", side="left"),
        yaxis2=dict(title="收益率(%)", side="right", overlaying="y"),
        legend=dict(x=0.01, y=0.99)
    )
    st.plotly_chart(config_chart(fig), use_container_width=True)

# 页脚
st.divider()
st.markdown("""
<div style='text-align: center; color: #64748b; font-size: 14px;'>
    数据来源：Yahoo Finance、FRED | 数据仅供参考，不构成投资建议
</div>
""", unsafe_allow_html=True)
