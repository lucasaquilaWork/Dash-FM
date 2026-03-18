import streamlit as st
import pandas as pd

st.title("📊 Dashboard Volumetria")

url = "https://docs.google.com/spreadsheets/d/SEU_ID/export?format=csv"

df = pd.read_csv(url)

st.dataframe(df)

st.bar_chart(df["PROGRAMADO"])
#123
