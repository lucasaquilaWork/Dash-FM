import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Dashboard Volumetria", layout="wide")

st.title("📦 Dashboard de Volumetria")

# -----------------------------
# 🔐 CONEXÃO COM GOOGLE SHEETS
# ----------------------------
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=scope
)

client = gspread.authorize(creds)

# 👉 COLOQUE AQUI O ID DA SUA PLANILHA
SPREADSHEET_ID = "1OtPl6T-ocUU9UVm81v4Feu-xX4OvLyuENLHutQwuiwA"

spreadsheet = client.open_by_key(SPREADSHEET_ID)

# -----------------------------
# 📥 FUNÇÃO PARA CARREGAR DADOS
# -----------------------------
@st.cache_data(ttl=600)
def carregar_dados():
    abas = spreadsheet.worksheets()
    dados_semanas = []

    for aba in abas:
        nome = aba.title

        # pegar só abas tipo W-12, W-13...
        if not nome.startswith("W-"):
            continue

        df_raw = pd.DataFrame(aba.get_all_records())

        # transformar estrutura
        df = df_raw.set_index(df_raw.columns[0]).T.reset_index()
        df = df.rename(columns={"index": "DATA"})

        # limpar números
        for col in df.columns[1:]:
            df[col] = (
                df[col]
                .astype(str)
                .str.replace(".", "", regex=False)
                .str.replace(",", ".", regex=False)
            )
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df["SEMANA"] = nome

        dados_semanas.append(df)

    df_final = pd.concat(dados_semanas, ignore_index=True)

    # converter data
    df_final["DATA"] = pd.to_datetime(df_final["DATA"], dayfirst=True)

    return df_final


df = carregar_dados()

# -----------------------------
# 🎛 FILTRO DE SEMANA
# -----------------------------
semanas = sorted(df["SEMANA"].unique())
semana_selecionada = st.selectbox("Selecione a semana", semanas)

df_semana = df[df["SEMANA"] == semana_selecionada]

# -----------------------------
# 📊 KPIs
# -----------------------------
st.subheader("📊 Indicadores")

col1, col2, col3 = st.columns(3)

col1.metric("Programado", f"{df_semana['PROGRAMADO'].sum():,.0f}")
col2.metric("Recebido", f"{df_semana['RECEBIDO'].sum():,.0f}")
col3.metric("Diferença", f"{df_semana['DIFERENÇA'].sum():,.0f}")

# -----------------------------
# 📈 GRÁFICO
# -----------------------------
st.subheader("📈 Programado x Recebido")

grafico = df_semana.set_index("DATA")[["PROGRAMADO", "RECEBIDO"]]

st.line_chart(grafico)

# -----------------------------
# 📦 BACKLOG
# -----------------------------
df_semana["BACKLOG"] = df_semana["PROGRAMADO"] - df_semana["RECEBIDO"]

st.subheader("📦 Backlog")

st.bar_chart(df_semana.set_index("DATA")["BACKLOG"])

# -----------------------------
# 📋 TABELA
# -----------------------------
st.subheader("📋 Dados detalhados")

st.dataframe(df_semana)
