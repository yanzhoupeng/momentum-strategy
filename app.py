# ============================================================
# 指数动量轮动策略 - 海外可用版
# 数据源：新浪(主) → 东财(备) → yfinance(兜底)
# ============================================================

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
# 用「指数代码」代替「ETF代码」
# 原因：指数数据源更丰富、更稳定，信号含义相同
INDEX_POOL = {
    # 中文显示名 → (新浪代码, 东财代码, yfinance代码)
    '沪深300':   ('sh000300',  '000300',  'ASHR'),
    '中证500':   ('sh000905',  '000905',  'CYB'),
    '创业板':    ('sz399006',  '399006',  'CHIR'),
    '中证1000':  ('sh000852',  '000852',  None),
    '纳斯达克':  (None,         None,      'QQQ'),
    '标普500':   (None,         None,      'SPY'),
    '医药':      ('sh000037',  '000037',  'XLV'),
    '半导体':    ('sz399811',  '399811',  'SMH'),
    '银行':      ('sh000036',  '000036',  None),
    '国债':      ('sh000012',  '000012',  'AGG'),   # 国债指数，避险用
}

# 侧边栏
st.sidebar.header("⚙️ 策略参数")
momentum_window = st.sidebar.slider("动量回看窗口", 5, 60, 20)
momentum_threshold = st.sidebar.slider("动量门槛", -0.05, 0.05, 0.0, 0.005)
switch_buffer = st.sidebar.slider("换仓缓冲", 0.0, 0.10, 0.02, 0.005)
ma_long_period = st.sidebar.slider("长均线周期", 60, 250, 120)

current_holding = st.sidebar.selectbox(
    "当前持仓", options=["未建仓"] + list(INDEX_POOL.keys()), index=0)
if current_holding == "未建仓":
    current_holding = None

# ============================================================
# 数据获取：三层兜底
# ============================================================
@st.cache_data(ttl=1800, show_spinner=False)
def fetch_single_index(name, codes, retries=2):
    """
    三层兜底获取指数数据：
    1. 新浪（akshare stock_zh_index_daily）
    2. 东财（akshare index_zh_a_hist）
    3. yfinance（美国上市ETF替代）
    """
    sina_code, em_code, yf_code = codes
    errors = []

    # --- 第1层：新浪 ---
    if sina_code:
        for attempt in range(retries):
            try:
                import akshare as ak
                df = ak.stock_zh_index_daily(symbol=sina_code)
                if df is not None and len(df) > 0:
                    df['date'] = pd.to_datetime(df['date'])
                    df = df.set_index('date').sort_index().tail(250)
                    return df['close'], "新浪 ✅"
            except Exception as e:
                errors.append(f"新浪(attempt{attempt+1}): {str(e)[:60]}")
            time.sleep(0.5)

    # --- 第2层：东财 ---
    if em_code:
        for attempt in range(retries):
            try:
                import akshare as ak
                df = ak.index_zh_a_hist(symbol=em_code, period='daily')
                if df is not None and len(df) > 0:
                    date_col = '日期' if '日期' in df.columns else df.columns[0]
                    close_col = '收盘' if '收盘' in df.columns else df.columns[1]
                    df[date_col] = pd.to_datetime(df[date_col])
                    df = df.set_index(date_col).sort_index().tail(250)
                    return df[close_col], "东财 ✅"
            except Exception as e:
                errors.append(f"东财(attempt{attempt+1}): {str(e)[:60]}")
            time.sleep(0.5)

    # --- 第3层：yfinance ---
    if yf_code:
        try:
            import yfinance as yf
