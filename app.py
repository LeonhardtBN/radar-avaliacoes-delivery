"""Dashboard do Radar de Avaliações. Rode com: streamlit run app.py"""

import os
from pathlib import Path

import altair as alt
import duckdb
import streamlit as st
from dotenv import load_dotenv

from radar import analise
from radar.config import CAMINHO_BANCO, MODELO_RESUMO, ROTULOS_TEMAS

load_dotenv()
st.set_page_config(page_title="Radar de Avaliações", layout="wide")
CORES = alt.Scale(domain=["iFood", "Rappi"], range=["#EA1D2C", "#FF8A00"])


@st.cache_resource
def conectar(caminho: str):
    return duckdb.connect(caminho, read_only=True)


st.title("Radar de Avaliações de Apps de Delivery")
st.caption("O que os clientes reclamam na Google Play, classificado por tema com IA (Gemini).")

if not Path(CAMINHO_BANCO).exists():
    st.error(f"Banco `{CAMINHO_BANCO}` não encontrado. Rode `python -m radar coletar` e "
             "`python -m radar classificar`, ou `python -m radar amostra` para testar.")
    st.stop()

con = conectar(CAMINHO_BANCO)
if con.execute("SELECT COUNT(*) FROM classificacoes").fetchall()[0][0] == 0:
    st.warning("Ainda não há avaliações classificadas. Rode `python -m radar classificar`.")
    st.stop()
if con.execute("SELECT COUNT(*) FROM classificacoes WHERE modelo = 'amostra'").fetchall()[0][0]:
    st.warning("Dados SINTÉTICOS (amostra). Os números não representam os apps reais.")

# ------------------------------------------------------------------ filtros
inicio_min, fim_max = analise.periodo(con)
apps_disponiveis = [r[0] for r in con.execute("SELECT DISTINCT app FROM avaliacoes ORDER BY lower(app)").fetchall()]
with st.sidebar:
    apps = st.multiselect("Apps", apps_disponiveis, default=apps_disponiveis)
    periodo = st.date_input("Período", (inicio_min, fim_max), min_value=inicio_min, max_value=fim_max)
    if st.button("Recarregar dados", width="stretch"):
        st.cache_resource.clear()
        st.rerun()
if not apps or len(periodo) != 2:
    st.info("Escolha pelo menos um app e um período completo.")
    st.stop()
inicio, fim = periodo

# ------------------------------------------------------------------ KPIs
kpis = analise.kpis(con, apps, inicio, fim)
colunas = st.columns(len(kpis))
for col, linha in zip(colunas, kpis.itertuples()):
    with col:
        st.subheader(linha.app)
        a, b, c = st.columns(3)
        a.metric("Avaliações", f"{linha.avaliacoes:,}".replace(",", "."))
        b.metric("Nota média", f"{linha.nota_media:.2f}".replace(".", ","))
        c.metric("Negativas", f"{linha.pct_negativas:.0f}%")

temas = analise.temas_negativos(con, apps, inicio, fim)
impacto = analise.impacto_na_nota(con, apps, inicio, fim)
cor = alt.Color("app:N", scale=CORES, title="App")

# ------------------------------------------------------------------ gráficos
esq, dir_ = st.columns(2)
with esq:
    st.markdown("#### Do que reclamam")
    st.caption("% das avaliações negativas de cada app que citam o tema")
    ordem = temas.groupby("tema_nome")["pct_das_negativas"].max().sort_values(ascending=False).index.tolist()
    st.altair_chart(alt.Chart(temas).mark_bar().encode(
        y=alt.Y("tema_nome:N", sort=ordem, title=None, axis=alt.Axis(labelLimit=240)),
        x=alt.X("pct_das_negativas:Q", title="% das negativas"),
        yOffset="app:N", color=cor,
        tooltip=["app", "tema_nome", "avaliacoes", "pct_das_negativas"],
    ).properties(height=34 * len(ordem) + 40), width="stretch")
with dir_:
    st.markdown("#### O que mais derruba a nota")
    st.caption("Nota média de quem cita o tema, menos a nota média do app")
    ordem_imp = impacto.groupby("tema_nome")["diferenca_vs_media"].min().sort_values().index.tolist()
    st.altair_chart(alt.Chart(impacto).mark_bar().encode(
        y=alt.Y("tema_nome:N", sort=ordem_imp, title=None, axis=alt.Axis(labelLimit=240)),
        x=alt.X("diferenca_vs_media:Q", title="Diferença na nota (estrelas)"),
        yOffset="app:N", color=cor,
        tooltip=["app", "tema_nome", "avaliacoes", "nota_media_tema", "diferenca_vs_media"],
    ).properties(height=34 * len(ordem_imp) + 40), width="stretch")

st.markdown("#### Tendência semanal e exemplos")
codigos = [t for t in ROTULOS_TEMAS if t not in ("elogio_geral", "outro")]
padrao = temas["tema"].iloc[0] if len(temas) else codigos[0]
tema = st.selectbox("Tema", codigos, index=codigos.index(padrao), format_func=ROTULOS_TEMAS.get)
tendencia = analise.tendencia_semanal(con, apps, inicio, fim, tema)
st.altair_chart(alt.Chart(tendencia).mark_line(point=True).encode(
    x=alt.X("semana:T", title="Semana"), y=alt.Y("pct_com_tema:Q", title="% das avaliações da semana"),
    color=cor, tooltip=["app", "semana", "avaliacoes", "pct_com_tema"],
).properties(height=260), width="stretch")
st.dataframe(analise.exemplos(con, apps, inicio, fim, tema), width="stretch", hide_index=True)

# ------------------------------------------------------------------ resumo com IA
st.markdown("#### Resumo para o time de produto")
if st.button(f"Gerar resumo com IA ({MODELO_RESUMO})"):
    if not os.getenv("GEMINI_API_KEY"):
        st.error("Defina GEMINI_API_KEY no .env para gerar o resumo.")
    else:
        from google.genai import errors

        from radar.gemini import cliente_padrao
        from radar.insights import gerar_resumo

        exemplos = {ROTULOS_TEMAS[t]: analise.exemplos(con, apps, inicio, fim, t, 5)["problema"].dropna().tolist()
                    for t in temas["tema"].drop_duplicates().head(4)}
        with st.spinner("Escrevendo o resumo..."):
            try:
                st.markdown(gerar_resumo(cliente_padrao(), kpis, temas, impacto, exemplos))
            except errors.APIError as e:
                st.error("Limite gratuito do Gemini atingido; tente em um minuto." if e.code == 429
                         else f"Erro na Gemini API ({e.code}).")
