# -*- coding: utf-8 -*-
# 指数动量轮动策略 - 海外可用版
# 数据源：新浪(主) → 东财(备) → yfinance(兜底)

import streamlit as st
import pandas as pd
import numpy as np
import time
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="动量轮动策略", page_icon="📈", layout="wide")
st.title("📈 指数动量轮动策略")
st.markdown("---")

# ============================================================
# 配置区
# ============================================================
INDEX_POOL = {
    "沪深300":  ("sh000300", "000300", "ASHR"),
    "中证500":  ("sh000905", "000905", None),
    "创业板":   ("sz399006", "399006", None),
    "中证1000": ("sh000852", "000852", None),
    "纳斯达克": (None,        None,     "QQQ"),
    "标普500":  (None,        None,     "SPY"),
    "医药":     ("sh000037", "000037", "XLV"),
    "半导体":   ("sz399811", "399811", "SMH"),
    "银行":     ("sh000036", "000036", None),
    "国债":     ("sh000012", "000012", "AGG"),
}

# 侧边栏参数
st.sidebar.header("⚙️ 策略参数")
momentum_window = st.sidebar.slider("动量回看窗口", 5, 60, 20)
momentum_threshold = st.sidebar.slider("动量门槛", -0.05, 0.05, 0.0, 0.005)
switch_buffer = st.sidebar.slider("换仓缓冲", 0.0, 0.10, 0.02, 0.005)
ma_long_period = st.sidebar.slider("长均线周期", 60, 250, 120)

current_holding = st.sidebar.selectbox(
    "当前持仓", options=["未建仓"] + list(INDEX_POOL.keys()), index=0
)
if current_holding == "未建仓":
    current_holding = None

# ============================================================
# 数据获取：三层兜底
# ============================================================
@st.cache_data(ttl=1800, show_spinner=False)
def fetch_single_index(name, codes, retries=2):
    sina_code, em_code, yf_code = codes
    errors = []

    # --- 第1层：新浪 ---
    if sina_code:
        for attempt in range(retries):
            try:
                import akshare as ak
                df = ak.stock_zh_index_daily(symbol=sina_code)
                if df is not None and len(df) > 0:
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.set_index("date").sort_index().tail(250)
                    return df["close"], "新浪 ✅"
            except Exception as e:
                errors.append("新浪(try%d): %s" % (attempt + 1, str(e)[:60]))
            time.sleep(0.5)

    # --- 第2层：东财 ---
    if em_code:
        for attempt in range(retries):
            try:
                import akshare as ak
                df = ak.index_zh_a_hist(symbol=em_code, period="daily")
                if df is not None and len(df) > 0:
                    date_col = "日期" if "日期" in df.columns else df.columns[0]
                    close_col = "收盘" if "收盘" in df.columns else df.columns[1]
                    df[date_col] = pd.to_datetime(df[date_col])
                    df = df.set_index(date_col).sort_index().tail(250)
                    return df[close_col], "东财 ✅"
            except Exception as e:
                errors.append("东财(try%d): %s" % (attempt + 1, str(e)[:60]))
            time.sleep(0.5)

    # --- 第3层：yfinance ---
    if yf_code:
        try:
            import yfinance as yf
            ticker = yf.Ticker(yf_code)
            df = ticker.history(period="1y")
            if df is not None and len(df) > 0:
                df.index = pd.to_datetime(df.index).tz_localize(None)
                df = df.sort_index().tail(250)
                return df["Close"], "yfinance(%s) ✅" % yf_code
        except Exception as e:
            errors.append("yfinance: %s" % str(e)[:60])

    return None, " | ".join(errors)


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_all_data():
    all_data = {}
    status = {}
    for name, codes in INDEX_POOL.items():
        series, info = fetch_single_index(name, codes)
        if series is not None:
            all_data[name] = series
            status[name] = info
        else:
            status[name] = "❌ " + info[:100]
        time.sleep(0.2)
    return pd.DataFrame(all_data), status


# ============================================================
# 获取数据
# ============================================================
with st.spinner("正在获取行情数据（多数据源尝试中，约需10-20秒）..."):
    df, status = fetch_all_data()

# 数据源状态
with st.expander("📡 数据获取状态（点击查看详情）"):
    for name, info in status.items():
        if "✅" in str(info):
            st.write("  %s: %s" % (name, info))
        else:
            st.error("  %s: %s" % (name, info))

if df is None or df.empty:
    st.error("❌ 所有数据源均获取失败")
    st.markdown("""
    **可能原因：** Streamlit Cloud 海外服务器被国内数据源屏蔽

    **解决方案：**
    1. 在本地电脑运行此程序（`streamlit run app.py`）
    2. 或将代码部署到国内云服务器
    """)
    st.stop()

success_count = len(df.columns)
total_count = len(INDEX_POOL)
st.success("✅ 数据获取完成！%d/%d 个标的成功，共 %d 个交易日" % (success_count, total_count, len(df)))

if success_count < total_count:
    missing = [n for n in INDEX_POOL if n not in df.columns]
    st.warning("⚠️ 缺失：%s" % ", ".join(missing))

st.caption("数据范围：%s ~ %s" % (df.index[0].strftime("%Y-%m-%d"), df.index[-1].strftime("%Y-%m-%d")))

# ============================================================
# 指标计算
# ============================================================
momentum = df.pct_change(periods=momentum_window)
ma_short = df.rolling(window=20).mean()
ma_long = df.rolling(window=ma_long_period).mean()

mom_today = momentum.iloc[-1]
price_today = df.iloc[-1]
ma_long_today = ma_long.iloc[-1]

# 动量排名（排除国债）
risk_assets = [name for name in df.columns if name != "国债"]
mom_risk = mom_today[risk_assets].dropna().sort_values(ascending=False)
best_etf = mom_risk.index[0] if len(mom_risk) > 0 else None
best_mom = mom_risk.iloc[0] if len(mom_risk) > 0 else -1

# 大盘趋势
broad = "沪深300" if "沪深300" in df.columns else (risk_assets[0] if risk_assets else None)
broad_above = False
if broad is not None and broad in ma_long_today.index:
    if not pd.isna(ma_long_today[broad]) and not pd.isna(price_today[broad]):
        broad_above = price_today[broad] > ma_long_today[broad]

# ============================================================
# 信号生成
# ============================================================
if best_etf is None or best_mom <= momentum_threshold:
    action = "🛡️ 持有国债（避险）"
    reason = "最强风险资产动量 %.2%% <= 门槛 %.1%%" % (best_mom * 100, momentum_threshold * 100)
    target = "国债"
elif not broad_above:
    action = "🛡️ 持有国债（避险）"
    reason = "%s 低于MA%d，大盘趋势偏空" % (broad, ma_long_period)
    target = "国债"
elif current_holding is None:
    action = "🟢 买入 %s" % best_etf
    reason = "首次建仓，动量最强=%s(%.2%%)" % (best_etf, best_mom * 100)
    target = best_etf
elif current_holding == best_etf:
    action = "🔵 继续持有 %s" % current_holding
    reason = "%s 仍为动量最强(%.2%%)" % (current_holding, best_mom * 100)
    target = current_holding
else:
    current_mom = mom_today.get(current_holding, 0)
    if pd.isna(current_mom):
        current_mom = -1
    if best_mom >= current_mom + switch_buffer:
        action = "🔴 换仓：%s → %s" % (current_holding, best_etf)
        reason = "%s动量(%.2%%) > %s(%.2%%)，差%.2%% >= 缓冲%.1%%" % (
            best_etf, best_mom * 100, current_holding, current_mom * 100,
            (best_mom - current_mom) * 100, switch_buffer * 100
        )
        target = best_etf
    else:
        action = "🔵 继续持有 %s" % current_holding
        reason = "%s动量仅高%.2%%，未达缓冲%.1%%" % (
            best_etf, (best_mom - current_mom) * 100, switch_buffer * 100
        )
        target = current_holding

# ============================================================
# 展示结果
# ============================================================
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("📅 最新日期", df.index[-1].strftime("%Y-%m-%d"))
with col2:
    st.metric("📊 当前持仓", current_holding or "未建仓")
with col3:
    emoji = "🟢多头" if broad_above else "🔴空头"
    st.metric("📈 大盘趋势", "%s(MA%d)" % (emoji, ma_long_period))

st.markdown("---")
st.markdown("## 📌 今日建议：%s" % action)
st.info("**原因：** %s" % reason)
st.markdown("---")

# 动量排名表
st.subheader("📊 动量排名（近%d日涨幅）" % momentum_window)
rank_data = []
for rank, (name, mom) in enumerate(mom_risk.items(), 1):
    marker = ""
    if name == current_holding:
        marker = "👈 当前持有"
    elif name == target and name != current_holding:
        marker = "👉 推荐标的"

    if name not in ma_long_today.index or pd.isna(ma_long_today[name]):
        ma_status = "数据不足"
    elif price_today[name] > ma_long_today[name]:
        ma_status = "价格>MA%d ✅" % ma_long_period
    else:
        ma_status = "价格<MA%d ❌" % ma_long_period

    rank_data.append({
        "排名": rank,
        "标的": name,
        "%d日涨幅" % momentum_window: "%.2f%%" % (mom * 100),
        "均线状态": ma_status,
        "备注": marker,
    })
st.dataframe(pd.DataFrame(rank_data), use_container_width=True, hide_index=True)

st.markdown("---")

# 走势图
st.subheader("📈 近60日走势（动量前3 + 国债）")
chart_cols = list(mom_risk.head(3).index)
if "国债" in df.columns:
    chart_cols.append("国债")
chart_cols = [c for c in chart_cols if c in df.columns]
if len(chart_cols) > 0:
    chart_data = df[chart_cols].tail(60).dropna()
    if len(chart_data) > 0:
        chart_norm = chart_data / chart_data.iloc[0] * 100
        st.line_chart(chart_norm, height=400)

st.markdown("---")

# 回测
st.subheader("📊 简单回测")
with st.spinner("回测中..."):
    daily_returns = df.pct_change()
    capital = 100000.0
    holding_bt = None
    pv_list = []
    trade_count = 0

    for i in range(len(df)):
        if i < momentum_window or i < ma_long_period:
            pv_list.append(capital)
            continue

        mom_bt = momentum.iloc[i]
        mom_risk_bt = mom_bt[risk_assets].dropna().sort_values(ascending=False)

        if len(mom_risk_bt) == 0:
            pv_list.append(capital)
            continue

        best_bt = mom_risk_bt.index[0]
        best_mom_bt = mom_risk_bt.iloc[0]

        broad_above_bt = False
        if broad is not None and broad in df.columns:
            ma_val = ma_long.iloc[i].get(broad, np.nan)
            price_val = df.iloc[i].get(broad, np.nan)
            if not pd.isna(ma_val) and not pd.isna(price_val):
                broad_above_bt = price_val > ma_val

        if best_mom_bt <= momentum_threshold or not broad_above_bt:
            tgt = "国债"
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

        if holding_bt is not None and holding_bt in daily_returns.columns:
            ret = daily_returns.iloc[i].get(holding_bt, 0)
            if pd.isna(ret):
                ret = 0
            capital *= (1 + ret)
        pv_list.append(capital)

    pv = pd.Series(pv_list, index=df.index)
    total_ret = capital / 100000 - 1
    years = len(df) / 250.0
    annual_ret = (1 + total_ret) ** (1 / years) - 1 if years > 0 else 0
    max_dd = ((pv / pv.cummax()) - 1).min()

    if "沪深300" in df.columns:
        hs300_ret = df["沪深300"].iloc[-1] / df["沪深300"].iloc[0] - 1
        hs300_annual = (1 + hs300_ret) ** (1 / years) - 1 if years > 0 else 0
        hs300_pv = 100000 * (df["沪深300"] / df["沪深300"].iloc[0])
        hs300_dd = ((hs300_pv / hs300_pv.cummax()) - 1).min()
    else:
        hs300_ret = hs300_annual = hs300_dd = 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("总收益", "%.2f%%" % (total_ret * 100), "沪深300: %.2f%%" % (hs300_ret * 100))
    with c2:
        st.metric("年化收益", "%.2f%%" % (annual_ret * 100), "沪深300: %.2f%%" % (hs300_annual * 100))
    with c3:
        st.metric("最大回撤", "%.2f%%" % (max_dd * 100), "沪深300: %.2f%%" % (hs300_dd * 100))
    with c4:
        st.metric("换仓次数", "%d次" % trade_count)

    nav_df = pd.DataFrame({"动量轮动": pv / 100000})
    if "沪深300" in df.columns:
        nav_df["沪深300"] = hs300_pv / 100000
    nav_df = nav_df.dropna()
    st.line_chart(nav_df, height=300)

st.markdown("---")
st.caption("⚠️ 以上仅为策略信号，不构成投资建议。数据源：新浪财经/东方财富/yfinance。")
