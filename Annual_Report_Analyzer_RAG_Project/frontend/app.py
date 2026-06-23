import os
import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="Annual Report Analyzer", layout="wide")
st.title("Annual Report Analyzer")

if st.button("Check backend"):
    try:
        r = httpx.get(f"{BACKEND_URL}/health", timeout=5)
        st.success(r.json())
    except Exception as exc:
        st.error(f"Backend unreachable: {exc}")