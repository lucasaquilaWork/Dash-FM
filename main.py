import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from datetime import datetime

st.set_page_config(page_title="Dashboard Volumetria", layout="wide")

st.title("📦 Dashboard de Volumetria")

# -----------------------------
# 🔐 CONEXÃO COM GOOGLE SHEETS
# -----------------------------
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=scope
)

client = gspread.authorize(creds)

SPREADSHEET_ID = "1OtPl6T-ocUU9UVm81v4Feu-xX4OvLyuENLHutQwuiwA"
spreadsheet = client.open_by_key(SPREADSHEET_ID)

# -----------------------------
# 📥 CARREGAR DADOS
# -----------------------------
@st.cache_data(ttl=600)
def carregar_dados():
    abas = spreadsheet.worksheets()
    dados_semanas = []

    for aba in abas:
        nome = aba.title

        if not nome.startswith("W-"):
            continue

        try:
            df_raw = pd.DataFrame(aba.get_all_records())

            if df_raw.empty:
                continue

            df = df_raw.set_index(df_raw.columns[0]).T.reset_index()
            df = df.rename(columns={"index": "DATA"})

            # padronizar colunas
            df.columns = (
                df.columns
                .str.strip()
                .str.upper()
                .str.replace(" ", "_")
            )

            # corrigir erro comum
            df = df.rename(columns={"PROGAMADO": "PROGRAMADO"})

            # limpar números
            for col in df.columns:
                if col not in ["DATA", "SEMANA"]:
                    df[col] = (
                        df[col]
                        .astype(str)
                        .str.replace(".", "", regex=False)
                        .str.replace(",", ".", regex=False)
                    )
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            df["SEMANA"] = nome

            dados_semanas.append(df)

        except Exception as e:
            st.write(f"Erro na aba {nome}: {e}")

    df_final = pd.concat(dados_semanas, ignore_index=True)

    # corrigir DATA
    ano = datetime.now().year
    df_final["DATA"] = df_final["DATA"].astype(str).str.strip()
    df_final["DATA"] = df_final["DATA"] + f"/{ano}"

    df_final["DATA"] = pd.to_datetime(
        df_final["DATA"],
        format="%d/%m/%Y",
        errors="coerce"
    )

    df_final = df_final.dropna(subset=["DATA"])

    return df_final


df = carregar_dados()

# -----------------------------
# 🎛 FILTRO DE SEMANA
# -----------------------------
semanas = sorted(df["SEMANA"].unique())
semana_selecionada = st.selectbox("Selecione a semana", semanas)

df_semana = df[df["SEMANA"] == semana_selecionada]

# -----------------------------
# 📅 FILTRO DE DIA
# -----------------------------
dias = df_semana["DATA"].dt.strftime("%d/%m").unique().tolist()
dias = sorted(dias, key=lambda x: pd.to_datetime(x, format="%d/%m"))

opcoes = ["TOTAL"] + dias

dia_selecionado = st.selectbox("Selecione o dia", opcoes)

if dia_selecionado != "TOTAL":
    df_filtrado = df_semana[
        df_semana["DATA"].dt.strftime("%d/%m") == dia_selecionado
    ]
else:
    df_filtrado = df_semana

# -----------------------------
# 📊 KPIs
# -----------------------------
st.subheader("📊 Indicadores")

col1, col2, col3 = st.columns(3)

col1.metric("Programado", f"{df_filtrado['PROGRAMADO'].sum():,.0f}")
col2.metric("Recebido", f"{df_filtrado['RECEBIDO'].sum():,.0f}")
col3.metric("Diferença", f"{df_filtrado['DIFERENÇA'].sum():,.0f}")

# -----------------------------
# 📊 GRÁFICO 1 - BARRA COMPARATIVA
# -----------------------------
st.subheader("📊 Programado x Recebido por Dia")

st.bar_chart(
    df_semana.set_index("DATA")[["PROGRAMADO", "RECEBIDO"]]
)

# -----------------------------
# 📉 GRÁFICO 2 - DIFERENÇA
# -----------------------------
st.subheader("📉 Diferença por Dia")

st.bar_chart(
    df_semana.set_index("DATA")["DIFERENÇA"]
)

# -----------------------------
# 📦 GRÁFICO 3 - BACKLOG
# -----------------------------
df_backlog = df_semana.copy()
df_backlog["BACKLOG"] = df_backlog["PROGRAMADO"] - df_backlog["RECEBIDO"]

st.subheader("📦 Backlog por Dia")

st.bar_chart(
    df_backlog.set_index("DATA")["BACKLOG"]
)

# -----------------------------
# 📊 GRÁFICO 4 - TOTAL SEMANA
# -----------------------------
st.subheader("📊 Total da Semana")

totais = df_semana[["PROGRAMADO", "RECEBIDO", "DIFERENÇA"]].sum()

st.bar_chart(totais)

# -----------------------------
# 📈 GRÁFICO 5 - ACUMULADO
# -----------------------------
st.subheader("📈 Acumulado da Semana")

df_acum = df_semana.sort_values("DATA").copy()

df_acum["PROG_ACUM"] = df_acum["PROGRAMADO"].cumsum()
df_acum["REC_ACUM"] = df_acum["RECEBIDO"].cumsum()

st.line_chart(
    df_acum.set_index("DATA")[["PROG_ACUM", "REC_ACUM"]]
)

# -----------------------------
# 📋 TABELA
# -----------------------------
st.subheader("📋 Dados detalhados")

st.dataframe(df_filtrado)
