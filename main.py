import streamlit as st
import gspread
import pandas as pd
import plotly.express as px
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

            df.columns = (
                df.columns
                .str.strip()
                .str.upper()
                .str.replace(" ", "_")
            )

            df = df.rename(columns={"PROGAMADO": "PROGRAMADO"})

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
# 🎛 FILTROS
# -----------------------------
semanas = sorted(df["SEMANA"].unique())
semana_selecionada = st.selectbox("Semana", semanas)

df_semana = df[df["SEMANA"] == semana_selecionada]

dias = df_semana["DATA"].dt.strftime("%d/%m").unique().tolist()
dias = sorted(dias, key=lambda x: pd.to_datetime(x, format="%d/%m"))

dia_selecionado = st.selectbox("Dia", ["TOTAL"] + dias)

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

prog = df_filtrado["PROGRAMADO"].sum()
rec = df_filtrado["RECEBIDO"].sum()
dif = df_filtrado["DIFERENÇA"].sum()

col1, col2, col3 = st.columns(3)
col1.metric("Programado", f"{prog:,.0f}")
col2.metric("Recebido", f"{rec:,.0f}")
col3.metric("Diferença", f"{dif:,.0f}")

# =============================
# 🧠 LÓGICA INTELIGENTE DE VISÃO
# =============================

df_plot = df_filtrado.copy()
df_plot["DATA_STR"] = df_plot["DATA"].dt.strftime("%d/%m")

# -----------------------------
# 🔎 VISÃO POR DIA
# -----------------------------
if dia_selecionado != "TOTAL":

    st.warning("📍 Visualizando um único dia")

    col1, col2 = st.columns(2)

    with col1:
        fig = px.bar(
            df_plot.melt(
                id_vars="DATA_STR",
                value_vars=["PROGRAMADO", "RECEBIDO"],
                var_name="TIPO",
                value_name="VALOR"
            ),
            x="TIPO",
            y="VALOR",
            color="TIPO",
            color_discrete_map={
                "PROGRAMADO": "#1f77b4",
                "RECEBIDO": "#2ca02c"
            },
            title="Programado vs Recebido"
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = px.bar(
            df_plot,
            x="DATA_STR",
            y="DIFERENÇA",
            color=df_plot["DIFERENÇA"].apply(lambda x: "Positivo" if x >= 0 else "Negativo"),
            color_discrete_map={
                "Positivo": "green",
                "Negativo": "red"
            },
            title="Diferença"
        )
        st.plotly_chart(fig, use_container_width=True)

# -----------------------------
# 📊 VISÃO TOTAL DA SEMANA
# -----------------------------
else:

    st.success("📊 Visualização completa da semana")

    # Programado vs Recebido
    st.subheader("📊 Programado x Recebido")

    fig = px.bar(
        df_plot.melt(
            id_vars="DATA_STR",
            value_vars=["PROGRAMADO", "RECEBIDO"],
            var_name="TIPO",
            value_name="VALOR"
        ),
        x="DATA_STR",
        y="VALOR",
        color="TIPO",
        barmode="group",
        color_discrete_map={
            "PROGRAMADO": "#1f77b4",
            "RECEBIDO": "#2ca02c"
        }
    )
    st.plotly_chart(fig, use_container_width=True)

    # Diferença
    st.subheader("📉 Diferença")

    df_plot["COR"] = df_plot["DIFERENÇA"].apply(
        lambda x: "Positivo" if x >= 0 else "Negativo"
    )

    fig = px.bar(
        df_plot,
        x="DATA_STR",
        y="DIFERENÇA",
        color="COR",
        color_discrete_map={
            "Positivo": "green",
            "Negativo": "red"
        }
    )
    st.plotly_chart(fig, use_container_width=True)

    # Backlog
    st.subheader("📦 Backlog")

    df_plot["BACKLOG"] = df_plot["PROGRAMADO"] - df_plot["RECEBIDO"]

    fig = px.bar(
        df_plot,
        x="DATA_STR",
        y="BACKLOG",
        color_discrete_sequence=["orange"]
    )
    st.plotly_chart(fig, use_container_width=True)

    # Total
    st.subheader("📊 Total da Semana")

    totais = df_plot[["PROGRAMADO", "RECEBIDO", "DIFERENÇA"]].sum().reset_index()
    totais.columns = ["TIPO", "VALOR"]

    fig = px.bar(
        totais,
        x="TIPO",
        y="VALOR",
        color="TIPO",
        color_discrete_map={
            "PROGRAMADO": "#1f77b4",
            "RECEBIDO": "#2ca02c",
            "DIFERENÇA": "#d62728"
        }
    )
    st.plotly_chart(fig, use_container_width=True)

    # Acumulado
    st.subheader("📈 Acumulado")

    df_acum = df_plot.sort_values("DATA").copy()
    df_acum["PROG_ACUM"] = df_acum["PROGRAMADO"].cumsum()
    df_acum["REC_ACUM"] = df_acum["RECEBIDO"].cumsum()

    fig = px.line(
        df_acum.melt(
            id_vars="DATA_STR",
            value_vars=["PROG_ACUM", "REC_ACUM"],
            var_name="TIPO",
            value_name="VALOR"
        ),
        x="DATA_STR",
        y="VALOR",
        color="TIPO",
        color_discrete_map={
            "PROG_ACUM": "#1f77b4",
            "REC_ACUM": "#2ca02c"
        }
    )
    st.plotly_chart(fig, use_container_width=True)

# -----------------------------
# 📋 TABELA
# -----------------------------
st.subheader("📋 Dados")
st.dataframe(df_filtrado)
