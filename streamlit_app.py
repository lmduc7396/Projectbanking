import streamlit as st


st.set_page_config(
    page_title="Banking Analysis Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

try:
    st.switch_page("pages/1_Banking_Charts.py")
except Exception:
    st.title("Banking Analysis Dashboard")
    st.markdown(
        """
        Unable to automatically open `pages/1_Banking_Charts.py`.
        Use the sidebar to navigate to the **Banking Charts** page.
        """
    )
