# ============================================================
# 指数动量轮动策略 - Streamlit 网页版
# 部署到 Streamlit Cloud 后，手机/iPad/电脑浏览器均可访问
# ============================================================
#
# 部署步骤：
# 1. 注册 GitHub 账号（如果还没有）
# 2. 把这个文件上传到 GitHub 仓库
# 3. 去 https://share.streamlit.io 部署（免费）
# 4. 部署后会给你一个网址，手机浏览器收藏即可
#
# 本地运行：pip install streamlit akshare pandas numpy
#           streamlit run app.py
# ============================================================

import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# 页面配置
# ============================================================
st.set_page_config(
    page_title="动量轮动策略",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📈 指数动量轮动策略")
st.markdown("---")

# ============================================================
# 侧边栏配置
# ============================================================
st.sidebar.header("⚙️ 策略参数")

ETF_POOL = {
    '510300': '沪深300ETF',
    '510500': '中证500ETF',
    '159915': '创业板ETF',
    '512100': '中证1000ETF',
    '513100': '纳指ETF',
    '513500': '标普500ETF',
    '159937': '医药ETF',
    '512480': '半导体ETF',
    '512800': '银行ETF',
    '511260': '国债ETF',
}

momentum_window = st.sidebar.slider("动量回看窗口（交易日）", 5, 60, 20)
momentum_threshold = st.sidebar.slider("动量门槛", -0.05, 0.05, 0.0, 0.005)
switch_buffer = st.sidebar.slider("换仓缓冲", 0.0, 0.10, 0.02, 0.005)
ma_long_period = st.sidebar.slider("长均线周期", 60, 250, 120)

current_holding = st.sidebar.selectbox(
    "当前持仓",
    options=["未建仓"] + list(ETF_POOL.values()),
    index=0
)
if current_holding == "未建仓":
    current_holding = None

# ============================================================
# 数据获取（带缓存）
# ============================================================
@st.cache_data(ttl=3600)  # 缓存1小时，避免频繁请求
def fetch_etf_data(etf_code, days=250):
    """获取ETF历史数据"""
    try:
        df = ak.fund_etf_hist_em(symbol=etf_code, period='daily', adjust='qfq')
        df['日期'] = pd.to_datetime(df['日期'])
        df = df.set_index('日期').sort_index()
        df = df.tail(days)
        return df['收盘']
    except:
        return None

@st.cache_data(ttl=3600)
def fetch_all_data():
    """获取所有ETF数据"""
    all_data = {}
    failed = []
    for code, name in ETF_POOL.items():
        series = fetch_etf_data(code, 250)
        if series is not None:
            all_data[name] = series
        else:
            failed.append(name)
    return pd.DataFrame(all_data), failed

# ============================================================
# 获取数据
# ============================================================
with st.spinner("正在获取行情数据..."):
    df, failed_etfs = fetch_all_data()

if df is None or df.empty:
    st.error("❌ 数据获取失败，请稍后重试")
    st.stop()

if failed_etfs:
    st.warning(f"⚠️ 以下标的获取失败：{', '.join(failed_etfs)}")

st.success(f"✅ 数据获取完成！共 {len(df)} 个交易日，{len(df.columns)} 个标的")
st.caption(f"数据范围：{df.index[0].strftime('%Y-%m-%d')} ~ {df.index[-1].strftime('%Y-%m-%d')}")

# ============================================================
# 指标计算
# ============================================================
momentum = df.pct_change(periods=momentum_window)
ma_short = df.rolling(window=20).mean()
ma_long = df.rolling(window=ma_long_period).mean()

mom_today = momentum.iloc[-1]
price_today = df.iloc[-1]
ma_short_today = ma_short.iloc[-1]
ma_long_today = ma_long.iloc[-1]

# 动量排名
risk_assets = [name for name in df.columns if name != '国债ETF']
mom_risk = mom_today[risk_assets].dropna().sort_values(ascending=False)
best_etf = mom_risk.index[0] if len(mom_risk) > 0 else None
best_mom = mom_risk.iloc[0] if len(mom_risk) > 0 else -1

# 大盘趋势
broad_market = '沪深300ETF' if '沪深300ETF' in df.columns else risk_assets[0]
broad_above_ma = price_today[broad_market] > ma_long_today[broad_market] if broad_market in df.columns else True

# ============================================================
# 信号生成
# ============================================================
if best_mom <= momentum_threshold:
    action = "🛡️ 持有国债ETF（避险）"
    reason = f"最强风险资产 {best_etf} 动量={best_mom:.2%} ≤ 门槛{momentum_threshold:.1%}"
    target = '国债ETF'
elif not broad_above_ma:
    action = "🛡️ 持有国债ETF（避险）"
    reason = f"{broad_market} 低于MA{ma_long_period}，大盘趋势偏空"
    target = '国债ETF'
elif current_holding is None:
    action = f"🟢 买入 {best_etf}"
    reason = f"首次建仓，动量最强={best_etf}({best_mom:.2%})"
    target = best_etf
elif current_holding == best_etf:
    action = f"🔵 继续持有 {current_holding}"
    reason = f"{current_holding} 仍为动量最强({best_mom:.2%})"
    target = current_holding
else:
    current_mom = mom_today.get(current_holding, 0)
    if pd.isna(current_mom):
        current_mom = -1
    if best_mom >= current_mom + switch_buffer:
        action = f"🔴 换仓：{current_holding} → {best_etf}"
        reason = f"{best_etf}动量({best_mom:.2%}) 超过 {current_holding}({current_mom:.2%})，达{best_mom-current_mom:.2%} ≥ 缓冲{switch_buffer:.1%}"
        target = best_etf
    else:
        action = f"🔵 继续持有 {current_holding}"
        reason = f"{best_etf}动量仅高{best_mom-current_mom:.2%}，未达换仓缓冲{switch_buffer:.1%}"
        target = current_holding

# ============================================================
# 展示结果
# ============================================================
col1, col2, col3 = st.columns(3)

with col1:
    st.metric("📅 最新日期", df.index[-1].strftime('%Y-%m-%d'))
with col2:
    st.metric("📊 当前持仓", current_holding or "未建仓")
with col3:
    trend_emoji = "🟢多头" if broad_above_ma else "🔴空头"
    st.metric("📈 大盘趋势", f"{trend_emoji}(MA{ma_long_period})")

st.markdown("---")

# 核心信号
st.markdown(f"## 📌 今日建议：{action}")
st.info(f"**原因：** {reason}")

st.markdown("---")

# 动量排名表
st.subheader("📊 动量排名（近{}日涨幅）".format(momentum_window))

rank_data = []
for rank, (name, mom) in enumerate(mom_risk.items(), 1):
    marker = ""
    if name == current_holding:
        marker = "👈 当前持有"
    elif name == target and name != current_holding:
        marker = "👉 推荐标的"
    
    # 均线状态
    if pd.isna(ma_short_today[name]) or pd.isna(ma_long_today[name]):
        ma_status = "数据不足"
    elif price_today[name] > ma_short_today[name] > ma_long_today[name]:
        ma_status = "多头 ↑"
    elif price_today[name] < ma_short_today[name] < ma_long_today[name]:
        ma_status = "空头 ↓"
    else:
        ma_status = "震荡 ≈"
    
    rank_data.append({
        '排名': rank,
        '标的': name,
        f'{momentum_window}日涨幅': f"{mom:.2%}",
        '均线状态': ma_status,
        '备注': marker,
    })

rank_df = pd.DataFrame(rank_data)
st.dataframe(rank_df, use_container_width=True, hide_index=True)

st.markdown("---")

# 价格走势图（选前3名）
st.subheader("📈 近期走势（动量前3名 + 国债ETF）")
top3 = list(mom_risk.head(3).index)
chart_cols = top3 + (['国债ETF'] if '国债ETF' in df.columns else [])
chart_data = df[chart_cols].tail(60)

# 归一化到100起点
chart_normalized = chart_data / chart_data.iloc[0] * 100

st.line_chart(chart_normalized, height=400)

st.markdown("---")

# 回测
st.subheader("📊 简单回测")

with st.spinner("回测中..."):
    daily_returns = df.pct_change()
    capital = 100000
    holding_bt = None
    portfolio_values = []
    trade_count = 0
    
    for i in range(len(df)):
        if i < momentum_window or i < ma_long_period:
            portfolio_values.append(capital)
            continue
        
        mom_bt = momentum.iloc[i]
        price_bt = df.iloc[i]
        mom_risk_bt = mom_bt[risk_assets].dropna().sort_values(ascending=False)
        
        if len(mom_risk_bt) == 0:
            portfolio_values.append(capital)
            continue
        
        best_bt = mom_risk_bt.index[0]
        best_mom_bt = mom_risk_bt.iloc[0]
        broad_above_bt = price_bt[broad_market] > ma_long.iloc[i][broad_market] if broad_market in df.columns else True
        
        if best_mom_bt <= momentum_threshold or not broad_above_bt:
            tgt = '国债ETF'
        elif holding_bt is None:
            tgt = best_bt
        elif best_bt == holding_bt:
            tgt = holding_bt
        elif best_mom_bt >= mom_bt.get(holding_bt, -1) + switch_buffer:
            tgt = best_bt
        else:
            tgt = holding_bt
        
        if holding_bt != tgt and holding_bt is not None:
            trade_count += 1
        holding_bt = tgt
        
        if holding_bt and holding_bt in daily_returns.columns:
            ret = daily_returns.iloc[i].get(holding_bt, 0)
            if pd.isna(ret):
                ret = 0
            capital *= (1 + ret)
        portfolio_values.append(capital)
    
    pv = pd.Series(portfolio_values, index=df.index)
    total_ret = capital / 100000 - 1
    years = len(df) / 250
    annual_ret = (1 + total_ret) ** (1/years) - 1 if years > 0 else 0
    max_dd = ((pv / pv.cummax()) - 1).min()
    
    # 沪深300对比
    if '沪深300ETF' in df.columns:
        hs300_ret = df['沪深300ETF'].iloc[-1] / df['沪深300ETF'].iloc[0] - 1
        hs300_annual = (1 + hs300_ret) ** (1/years) - 1 if years > 0 else 0
        hs300_pv = 100000 * (df['沪深300ETF'] / df['沪深300ETF'].iloc[0])
        hs300_dd = ((hs300_pv / hs300_pv.cummax()) - 1).min()
    else:
        hs300_ret = hs300_annual = hs300_dd = 0
    
    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a:
        st.metric("总收益", f"{total_ret:.2%}", f"沪深300: {hs300_ret:.2%}")
    with col_b:
        st.metric("年化收益", f"{annual_ret:.2%}", f"沪深300: {hs300_annual:.2%}")
    with col_c:
        st.metric("最大回撤", f"{max_dd:.2%}", f"沪深300: {hs300_dd:.2%}")
    with col_d:
        st.metric("换仓次数", f"{trade_count}次")
    
    # 净值曲线
    nav_df = pd.DataFrame({
        '动量轮动': pv / 100000,
        '沪深300': hs300_pv / 100000 if '沪深300ETF' in df.columns else None
    }).dropna()
    st.line_chart(nav_df, height=300)

st.markdown("---")
st.caption("⚠️ 以上仅为策略信号，不构成投资建议。数据来源：东方财富（通过akshare获取）。")
