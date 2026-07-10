 # ============================================================
# 诊断版：测试 akshare 接口到底出了什么问题
# ============================================================
import streamlit as st
import pandas as pd
import traceback

st.title("🔧 akshare 接口诊断")

# 测试1：检查 akshare 是否安装成功
st.header("1️⃣ 检查 akshare 安装")
try:
    import akshare as ak
    st.success(f"akshare 版本：{ak.__version__}")
except ImportError as e:
    st.error(f"akshare 未安装：{e}")
    st.stop()

# 测试2：逐个测试 ETF 数据获取
st.header("2️⃣ 逐个测试 ETF 数据获取")

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

for code, name in ETF_POOL.items():
    st.write(f"**测试 {name}({code})...**")
    try:
        df = ak.fund_etf_hist_em(symbol=code, period='daily', adjust='qfq')
        if df is None or len(df) == 0:
            st.warning(f"  ⚠️ 接口返回了空数据")
        else:
            st.write(f"  ✅ 成功！{len(df)}条数据")
            st.write(f"  列名：{list(df.columns)}")
            st.write(f"  前2行：")
            st.dataframe(df.head(2))
            st.write(f"  最后日期：{df.iloc[-1, 0]}")
    except Exception as e:
        st.error(f"  ❌ 失败：{type(e).__name__}: {e}")
        st.code(traceback.format_exc())
    st.write("---")
