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

# 全局样式（参考参考站的清晰视觉）
st.markdown("""
<style>
/* 卡片样式：参考站的圆角+浅背景+清晰层级 */
.metric-card {
    background: #f8fafc;
    border-radius: 12px;
    padding: 18px;
    border: 1px solid #e2e8f0;
    margin-bottom: 12px;
    transition: all 0.2s;
}
.metric-card:hover {
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}
/* 数值样式：大字体+加粗，参考站的突出显示 */
.metric-value {
    font-size: 28px;
    font-weight: 800;
    color: #0f172a;
    margin: 8px 0;
}
/* 涨跌幅样式：涨红跌绿，强视觉区分 */
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
/* 标题样式 */
.module-title {
    font-size: 22px;
    font-weight: 700;
    color: #0f172a;
    margin: 24px 0 16px 0;
}
/* 页面边距优化 */
.block-container {
    padding-top: 2rem;
    padding-left: 3rem;
    padding-right: 3rem;
}
</style>
""", unsafe_allow_html=True)

# ===================== 密钥配置（仅需替换这里的FRED密钥） =====================
FRED_API_KEY = "cc31d1914c0dd0e60a7f384aefdeec52"
# 初始化FRED
fred = None
if FRED_API_KEY and FRED_API_KEY != "你的FRED密钥":
    try:
        fred = Fred(api_key=FRED_API_KEY)
    except:
        st.warning("FRED API初始化失败，美债相关数据将无法显示")
        fred = None

# ===================== 稳定工具函数（绝对不会报错） =====================
def get_latest_value(series):
    """安全获取最新值，转成纯Python float"""
    if series.empty:
        return 0.0
    latest = series.iloc[-1]
    return float(latest) if pd.notna(latest) else 0.0

def get_change_pct(series):
    """安全计算涨跌幅，转成纯Python float"""
    if len(series) < 2:
        return 0.0
    prev = float(series.iloc[-2])
    curr = float(series.iloc[-1])
    if pd.isna(prev) or pd.isna(curr) or prev == 0:
        return 0.0
    return round(((curr - prev) / prev) * 100, 2)

def get_change_color(pct):
    """获取涨跌幅颜色class"""
    if pct > 0:
        return "metric-up"
    elif pct < 0:
        return "metric-down"
    else:
        return "metric-flat"

def config_chart_hover(fig):
    """配置图表hover大字体，符合大屏需求"""
    fig.update_layout(
        hoverlabel=dict(
            font_size=18,
            font_weight="bold",
            bgcolor="#f8fafc",
            bordercolor="#e2e8f0",
            padding=10
        ),
        hovertemplate="<b>时间：%{x}</b><br>数值：<span style='font-size:20px; font-weight:800'>%{y}</span><extra></extra>",
        template="plotly_white",
        height=450,
        margin=dict(l=20, r=20, t=40, b=20)
    )
    return fig

# ===================== 数据加载（全模块补全+异常处理） =====================
@st.cache_data(ttl=300, show_spinner="正在加载全球市场数据...")
def load_all_data():
    data = {}
    # -------------------- 1. 全球股票数据 --------------------
    # A股指数
    a_stocks = {
        "上证指数": "sh000001",
        "深证成指": "sz399001",
        "创业板指": "sz399006",
        "沪深300": "sh000300"
    }
    for name, code in a_stocks.items():
        try:
            import requests
            resp = requests.get(f"https://hq.sinajs.cn/list={code}", timeout=5)
            raw_data = resp.text.split('"')[1].split(',')
            close = float(raw_data[3])
            prev_close = float(raw_data[2])
            # 构造Series，兼容图表
            data[f"a_{name}"] = pd.Series([prev_close, close])
        except:
            data[f"a_{name}"] = pd.Series([0.0, 0.0])
    
    # 美股指数
    us_stocks = {
        "道琼斯指数": "^DJI",
        "纳斯达克综指": "^IXIC",
        "标普500": "^GSPC",
        "纳斯达克100": "^NDX"
    }
    for name, code in us_stocks.items():
        try:
            df = yf.download(code, period="30d", progress=False, show_errors=False)
            data[f"us_{name}"] = df["Close"].dropna() if not df.empty else pd.Series([0.0]*30)
        except:
            data[f"us_{name}"] = pd.Series([0.0]*30)

    # -------------------- 2. 大宗商品数据 --------------------
    commodities = {
        # 贵金属
        "黄金": "GC=F",
        "白银": "SI=F",
        # 工业金属
        "铜": "HG=F",
        "铝": "ALI=F",
        "锌": "ZS=F",
        # 能源
        "WTI原油": "CL=F",
        "布伦特原油": "BZ=F",
        "天然气": "NG=F"
    }
    for name, code in commodities.items():
        try:
            df = yf.download(code, period="30d", progress=False, show_errors=False)
            data[f"comm_{name}"] = df["Close"].dropna() if not df.empty else pd.Series([0.0]*30)
        except:
            data[f"comm_{name}"] = pd.Series([0.0]*30)

    # -------------------- 3. 美元美债数据 --------------------
    # 美元指数
    try:
        dxy_df = yf.download("DX-Y.NYB", period="30d", progress=False, show_errors=False)
        data["dxy"] = dxy_df["Close"].dropna() if not dxy_df.empty else pd.Series([0.0]*30)
    except:
        data["dxy"] = pd.Series([0.0]*30)
    
    # 美元兑人民币
    try:
        import requests
        resp = requests.get("https://hq.sinajs.cn/list=fx_susdcny", timeout=5)
        raw_data = resp.text.split('"')[1].split(',')
        close = float(raw_data[1])
        prev_close = float(raw_data[2])
        data["usd_cny"] = pd.Series([prev_close, close])
    except:
        data["usd_cny"] = pd.Series([0.0, 0.0])
    
    # 美债收益率
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
                data[f"bond_{name}"] = series if not series.empty else pd.Series([0.0]*30)
            else:
                data[f"bond_{name}"] = pd.Series([0.0]*30)
        except:
            data[f"bond_{name}"] = pd.Series([0.0]*30)
    
    return data

# 加载数据
with st.spinner("正在加载全球市场数据..."):
    market_data = load_all_data()

# ===================== 侧边栏导航 =====================
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

# ===================== 页面渲染（参考站的清晰布局） =====================
# -------------------- 1. 全球股票指数板块 --------------------
if selected_page == "📈 全球股票指数":
    st.title("📈 全球股票核心指数")
    st.divider()

    # A股指数卡片
    st.markdown("<div class='module-title'>🇨🇳 A股核心指数</div>", unsafe_allow_html=True)
    a_cols = st.columns(4)
    a_stock_list = ["上证指数", "深证成指", "创业板指", "沪深300"]
    for idx, name in enumerate(a_stock_list):
        with a_cols[idx]:
            series = market_data[f"a_{name}"]
            val = get_latest_value(series)
            pct = get_change_pct(series)
            color_class = get_change_color(pct)
            st.markdown(f"""
            <div class='metric-card'>
                <div style='font-size:16px; color:#475569; font-weight:600;'>{name}</div>
                <div class='metric-value'>{val:.2f}</div>
                <div class='{color_class}'>{pct:.2f}%</div>
            </div>
            """, unsafe_allow_html=True)

    # 美股指数卡片
    st.markdown("<div class='module-title'>🇺🇸 美股核心指数</div>", unsafe_allow_html=True)
    us_cols = st.columns(4)
    us_stock_list = ["道琼斯指数", "纳斯达克综指", "标普500", "纳斯达克100"]
    for idx, name in enumerate(us_stock_list):
        with us_cols[idx]:
            series = market_data[f"us_{name}"]
            val = get_latest_value(series)
            pct = get_change_pct(series)
            color_class = get_change_color(pct)
            st.markdown(f"""
            <div class='metric-card'>
                <div style='font-size:16px; color:#475569; font-weight:600;'>{name}</div>
                <div class='metric-value'>{val:.2f}</div>
                <div class='{color_class}'>{pct:.2f}%</div>
            </div>
            """, unsafe_allow_html=True)

    # 美股趋势图表
    st.markdown("<div class='module-title'>📈 美股指数30日走势</div>", unsafe_allow_html=True)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=market_data["us_纳斯达克综指"].index,
        y=market_data["us_纳斯达克综指"].values,
        name="纳斯达克综指",
        line=dict(color="#e63946", width=2.5)
    ))
    fig.add_trace(go.Scatter(
        x=market_data["us_标普500"].index,
        y=market_data["us_标普500"].values,
        name="标普500",
        line=dict(color="#22c55e", width=2.5)
    ))
    fig.add_trace(go.Scatter(
        x=market_data["us_道琼斯指数"].index,
        y=market_data["us_道琼斯指数"].values,
        name="道琼斯指数",
        line=dict(color="#3b82f6", width=2.5)
    ))
    fig.update_layout(title="纳斯达克综指 vs 标普500 vs 道琼斯指数", xaxis_title="日期", yaxis_title="指数点数")
    st.plotly_chart(config_chart_hover(fig), use_container_width=True)

# -------------------- 2. 大宗商品期货板块 --------------------
elif selected_page == "🛢️ 大宗商品期货":
    st.title("🛢️ 大宗商品期货监控")
    st.divider()

    # 贵金属卡片
    st.markdown("<div class='module-title'>🥇 贵金属</div>", unsafe_allow_html=True)
    metal_cols = st.columns(2)
    metal_list = ["黄金", "白银"]
    for idx, name in enumerate(metal_list):
        with metal_cols[idx]:
            series = market_data[f"comm_{name}"]
            val = get_latest_value(series)
            pct = get_change_pct(series)
            color_class = get_change_color(pct)
            unit = "USD/盎司"
            st.markdown(f"""
            <div class='metric-card'>
                <div style='font-size:16px; color:#475569; font-weight:600;'>{name}</div>
                <div class='metric-value'>{val:.2f}</div>
                <div style='font-size:14px; color:#64748b; margin-bottom:8px;'>{unit}</div>
                <div class='{color_class}'>{pct:.2f}%</div>
            </div>
            """, unsafe_allow_html=True)

    # 工业金属卡片
    st.markdown("<div class='module-title'>⚙️ 工业金属</div>", unsafe_allow_html=True)
    industry_cols = st.columns(3)
    industry_list = ["铜", "铝", "锌"]
    for idx, name in enumerate(industry_list):
        with industry_cols[idx]:
            series = market_data[f"comm_{name}"]
            val = get_latest_value(series)
            pct = get_change_pct(series)
            color_class = get_change_color(pct)
            unit = "USD/吨"
            st.markdown(f"""
            <div class='metric-card'>
                <div style='font-size:16px; color:#475569; font-weight:600;'>{name}</div>
                <div class='metric-value'>{val:.2f}</div>
                <div style='font-size:14px; color:#64748b; margin-bottom:8px;'>{unit}</div>
                <div class='{color_class}'>{pct:.2f}%</div>
            </div>
            """, unsafe_allow_html=True)

    # 能源卡片
    st.markdown("<div class='module-title'>⛽ 能源商品</div>", unsafe_allow_html=True)
    energy_cols = st.columns(3)
    energy_list = ["WTI原油", "布伦特原油", "天然气"]
    for idx, name in enumerate(energy_list):
        with energy_cols[idx]:
            series = market_data[f"comm_{name}"]
            val = get_latest_value(series)
            pct = get_change_pct(series)
            color_class = get_change_color(pct)
            unit = "USD/桶" if "原油" in name else "USD/MMBtu"
            st.markdown(f"""
            <div class='metric-card'>
                <div style='font-size:16px; color:#475569; font-weight:600;'>{name}</div>
                <div class='metric-value'>{val:.2f}</div>
                <div style='font-size:14px; color:#64748b; margin-bottom:8px;'>{unit}</div>
                <div class='{color_class}'>{pct:.2f}%</div>
            </div>
            """, unsafe_allow_html=True)

    # 黄金原油趋势图表
    st.markdown("<div class='module-title'>📈 黄金&原油30日走势</div>", unsafe_allow_html=True)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=market_data["comm_黄金"].index,
        y=market_data["comm_黄金"].values,
        name="黄金",
        line=dict(color="#f59e0b", width=2.5)
    ))
    fig.add_trace(go.Scatter(
        x=market_data["comm_WTI原油"].index,
        y=market_data["comm_WTI原油"].values,
        name="WTI原油",
        line=dict(color="#ef4444", width=2.5),
        yaxis="y2"
    ))
    fig.update_layout(
        title="黄金 vs WTI原油走势",
        xaxis_title="日期",
        yaxis=dict(title="黄金价格(USD/盎司)", side="left"),
        yaxis2=dict(title="原油价格(USD/桶)", side="right", overlaying="y"),
        legend=dict(x=0.01, y=0.99)
    )
    st.plotly_chart(config_chart_hover(fig), use_container_width=True)

# -------------------- 3. 美元&美债市场板块 --------------------
elif selected_page == "💵 美元&美债市场":
    st.title("💵 美元&美债市场监控")
    st.divider()

    # 美元相关卡片
    st.markdown("<div class='module-title'>💵 美元汇率</div>", unsafe_allow_html=True)
    usd_cols = st.columns(2)
    usd_list = [("美元指数(DXY)", "dxy"), ("美元兑人民币", "usd_cny")]
    for idx, (name, key) in enumerate(usd_list):
        with usd_cols[idx]:
            series = market_data[key]
            val = get_latest_value(series)
            pct = get_change_pct(series)
            color_class = get_change_color(pct)
            st.markdown(f"""
            <div class='metric-card'>
                <div style='font-size:16px; color:#475569; font-weight:600;'>{name}</div>
                <div class='metric-value'>{val:.4f}</div>
                <div class='{color_class}'>{pct:.2f}%</div>
            </div>
            """, unsafe_allow_html=True)

    # 美债收益率卡片
    st.markdown("<div class='module-title'>📜 美债收益率</div>", unsafe_allow_html=True)
    bond_cols = st.columns(4)
    bond_list = ["2年期美债收益率", "10年期美债收益率", "30年期美债收益率", "10年期实际利率"]
    for idx, name in enumerate(bond_list):
        with bond_cols[idx]:
            series = market_data[f"bond_{name}"]
            val = get_latest_value(series)
            pct = get_change_pct(series)
            color_class = get_change_color(pct)
            st.markdown(f"""
            <div class='metric-card'>
                <div style='font-size:16px; color:#475569; font-weight:600;'>{name}</div>
                <div class='metric-value'>{val:.2f}%</div>
                <div class='{color_class}'>{pct:.2f}%</div>
            </div>
            """, unsafe_allow_html=True)

    # 美元指数&美债收益率图表
    st.markdown("<div class='module-title'>📈 美元指数&10年期美债收益率30日走势</div>", unsafe_allow_html=True)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=market_data["dxy"].index,
        y=market_data["dxy"].values,
        name="美元指数",
        line=dict(color="#1e40af", width=2.5)
    ))
    fig.add_trace(go.Scatter(
        x=market_data["bond_10年期美债收益率"].index,
        y=market_data["bond_10年期美债收益率"].values,
        name="10年期美债收益率",
        line=dict(color="#dc2626", width=2.5),
        yaxis="y2"
    ))
    fig.update_layout(
        title="美元指数 vs 10年期美债收益率",
        xaxis_title="日期",
        yaxis=dict(title="美元指数", side="left"),
        yaxis2=dict(title="收益率(%)", side="right", overlaying="y"),
        legend=dict(x=0.01, y=0.99)
    )
    st.plotly_chart(config_chart_hover(fig), use_container_width=True)

# 页脚
st.divider()
st.markdown("""
<div style='text-align: center; color: #64748b; font-size: 14px;'>
    数据来源：新浪财经、Yahoo Finance、FRED | 数据仅供参考，不构成投资建议
</div>
""", unsafe_allow_html=True)
