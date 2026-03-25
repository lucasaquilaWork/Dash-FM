import streamlit as st
import gspread
import pandas as pd
import plotly.express as px
from google.oauth2.service_account import Credentials
from datetime import datetime
import time

st.set_page_config(page_title="Dashboard Volumetria", layout="wide")

st.title("📦 Dashboard de Volumetria")

# -----------------------------
# 🔄 BOTÃO DE ATUALIZAÇÃO
# -----------------------------
if st.button("🔄 Atualizar dados"):
    st.cache_data.clear()
    st.rerun()

# -----------------------------
# 🔐 CONEXÃO
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
# 📥 CARREGAR DADOS COM RETRY
# -----------------------------
@st.cache_data(ttl=600)
def carregar_dados():
    for tentativa in range(3):  # retry automático
        try:
            abas = spreadsheet.worksheets()
            dados_semanas = []

            for aba in abas:
                nome = aba.title

                if not nome.startswith("W-"):
                    continue

                try:
                    dados = aba.get_all_values()

                    if not dados or len(dados) < 2:
                        continue

                    df_raw = pd.DataFrame(dados)
                    df_raw = df_raw.replace("", None).dropna(how="all")

                    if df_raw.shape[1] < 2:
                        continue

                    df_raw.columns = df_raw.iloc[0]
                    df_raw = df_raw[1:]
                    df_raw = df_raw.replace("", None).dropna(how="all")

                    primeira_coluna = df_raw.columns[0]

                    df = df_raw.set_index(primeira_coluna).T.reset_index()
                    df.columns = ["DATA"] + list(df.columns[1:])

                    df.columns = (
                        pd.Index(df.columns)
                        .astype(str)
                        .str.strip()
                        .str.upper()
                        .str.replace(" ", "_")
                    )

                    df = df.rename(columns={"PROGAMADO": "PROGRAMADO"})

                    colunas_esperadas = ["PROGRAMADO", "RECEBIDO", "DIFERENÇA"]

                    if not all(col in df.columns for col in colunas_esperadas):
                        continue

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

                except:
                    continue

            if not dados_semanas:
                return pd.DataFrame()

            df_final = pd.concat(dados_semanas, ignore_index=True)

            # -----------------------------
            # 📅 TRATAMENTO DE DATA
            # -----------------------------
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

        except Exception as e:
            time.sleep(2)

    return pd.DataFrame()


# -----------------------------
# 🧠 LOAD COM PROTEÇÃO
# -----------------------------
try:
    with st.spinner("Carregando dados..."):
        df = carregar_dados()

    if df.empty:
        st.warning("⚠️ Sem dados disponíveis no momento")
        st.stop()

except Exception:
    st.error("❌ Erro ao carregar dados. Tente novamente.")
    st.stop()

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

# FAIL SAFE
if df_filtrado.empty:
    st.warning("⚠️ Sem dados para o filtro selecionado")
    st.stop()

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

df_plot = df_filtrado.copy()
df_plot["DATA_STR"] = df_plot["DATA"].dt.strftime("%d/%m")

# -----------------------------
# 🔎 VISÃO DIA (UNIFICADA)
# -----------------------------
if dia_selecionado != "TOTAL":

    st.warning("📍 Visualizando um único dia")

    # preparar dados
    df_dia = df_plot[["PROGRAMADO", "RECEBIDO", "DIFERENÇA"]].sum().reset_index()
    df_dia.columns = ["TIPO", "VALOR"]

    # cor inteligente
    def cor(row):
        if row["TIPO"] == "PROGRAMADO":
            return "#1f77b4"
        elif row["TIPO"] == "RECEBIDO":
            return "#2ca02c"
        else:
            return "green" if row["VALOR"] >= 0 else "red"

    df_dia["COR"] = df_dia.apply(cor, axis=1)

    # gráfico único
    fig = px.bar(
        df_dia,
        x="TIPO",
        y="VALOR",
        color="TIPO",
        text_auto=True,
        color_discrete_map={
            "PROGRAMADO": "#1f77b4",
            "RECEBIDO": "#2ca02c",
            "DIFERENÇA": "#d62728"
        }
    )

    # sobrescrever cor da diferença dinamicamente
    fig.for_each_trace(
        lambda t: t.update(marker_color=[
            df_dia[df_dia["TIPO"] == t.name]["COR"].values[0]
        ])
    )

    st.plotly_chart(fig, use_container_width=True)
# -----------------------------
# 📊 VISÃO SEMANA
# -----------------------------
else:

    st.success("📊 Visão completa da semana")

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

    totais = df_plot[["PROGRAMADO", "RECEBIDO", "DIFERENÇA"]].sum().reset_index()
    totais.columns = ["TIPO", "VALOR"]

    fig = px.bar(totais, x="TIPO", y="VALOR", color="TIPO")
    st.plotly_chart(fig, use_container_width=True)

# -----------------------------
# 📋 TABELA
# -----------------------------
st.subheader("📋 Dados")
st.dataframe(df_filtrado)
