
import streamlit as st
import pandas as pd
import plotly.express as px
from db import get_conn, put_conn

st.set_page_config(page_title="Dashboard de Pedidos", layout="wide", initial_sidebar_state="expanded")

# Estilo CSS para tooltips personalizados
st.markdown("""
<style>
.tooltip {
  position: relative;
  display: inline-block;
  cursor: pointer;
}

.tooltip .tooltiptext {
  visibility: hidden;
  width: 260px;
  background-color: rgba(60, 60, 60, 0.9);
  color: #fff;
  text-align: left;
  border-radius: 8px;
  padding: 10px;
  position: absolute;
  z-index: 1;
  bottom: 125%;
  left: 0%;
  opacity: 0;
  transition: opacity 0.3s;
  font-size: 13px;
}

.tooltip:hover .tooltiptext {
  visibility: visible;
  opacity: 1;
}
</style>
""", unsafe_allow_html=True)

# Conectar ao banco de dados
conn = get_conn()
query = "SELECT * FROM pedidos;"
df = pd.read_sql(query, conn)
put_conn(conn)

# Conversão de datas e colunas auxiliares
df['data_pedido'] = pd.to_datetime(df['data_pedido'])
df['ano'] = df['data_pedido'].dt.year
df['mes'] = df['data_pedido'].dt.month
df['ano_mes'] = df['data_pedido'].dt.to_period('M').astype(str)

# Filtros
with st.sidebar:
    st.title("Filtros")
    franqueados = st.multiselect("Franqueado", df["franqueado"].unique())
    fornecedores = st.multiselect("Fornecedor", df["fornecedor"].unique())
    status = st.multiselect("Status", df["status"].unique())
    anos = st.multiselect("Ano", sorted(df["ano"].unique()))
    meses = st.multiselect("Mês", sorted(df["mes"].unique()))
    st.markdown("---")

if franqueados:
    df = df[df["franqueado"].isin(franqueados)]
if fornecedores:
    df = df[df["fornecedor"].isin(fornecedores)]
if status:
    df = df[df["status"].isin(status)]
if anos:
    df = df[df["ano"].isin(anos)]
if meses:
    df = df[df["mes"].isin(meses)]

# Remover franqueados [Excluídos] das análises
df_franqueados_ativos = df[~df['franqueado'].str.contains(r'\[Excluído\]', case=False, na=False)]

# Título e KPIs
st.title("📦 Dashboard Analítico de Pedidos")
col1, col2, col3 = st.columns(3)
col1.metric("Total de Pedidos", len(df))
col2.metric("Valor Total", f"R${df['valor_pedido'].sum():,.2f}")
col3.metric("Franqueados Ativos", df_franqueados_ativos['franqueado'].nunique())

st.markdown("---")

# 📅 Total de Pedidos por Mês
st.markdown("""<h4>📅 Total de Pedidos por Mês
<span class="tooltip"> ℹ️
  <span class="tooltiptext">
    Agrupa todos os pedidos por mês e conta o total. Inclui todos os franqueados, inclusive os desativados.
  </span>
</span></h4>""", unsafe_allow_html=True)

df_mensal = df.groupby('ano_mes').agg({'numero_pedido': 'count'}).reset_index().rename(columns={'numero_pedido': 'total_pedidos'})
fig_trend = px.line(df_mensal, x='ano_mes', y='total_pedidos', markers=True, title="Evolução Mensal de Pedidos")
fig_trend.update_layout(xaxis_title="Mês", yaxis_title="Quantidade de Pedidos")
st.plotly_chart(fig_trend, use_container_width=True)

# 🏪 Top Franqueados
st.markdown("""<h4>🏪 Top Franqueados por Quantidade de Pedidos
<span class="tooltip"> ℹ️
  <span class="tooltiptext">
    Mostra os 10 franqueados com maior volume de pedidos no período selecionado. Ignora franqueados desativados.
  </span>
</span></h4>""", unsafe_allow_html=True)

df_rank = df_franqueados_ativos.groupby('franqueado')['numero_pedido'].count().reset_index(name='qtd_pedidos')
df_rank = df_rank.sort_values(by='qtd_pedidos', ascending=False).head(10)
fig_rank = px.bar(df_rank, x='franqueado', y='qtd_pedidos', title="Top 10 Franqueados")
st.plotly_chart(fig_rank, use_container_width=True)

# ⏱️ Tempo Médio Entre Pedidos
st.markdown("""<h4>⏱️ Tempo Médio Entre Pedidos por Franqueado
<span class="tooltip"> ℹ️
  <span class="tooltiptext">
    Calcula a média de dias entre os pedidos feitos por cada franqueado. Considera apenas franqueados ativos com 2 ou mais pedidos.
  </span>
</span></h4>""", unsafe_allow_html=True)

df_sorted = df_franqueados_ativos.sort_values(['franqueado', 'data_pedido'])
df_sorted['diff_dias'] = df_sorted.groupby('franqueado')['data_pedido'].diff().dt.days
df_tempo_medio = df_sorted.groupby('franqueado')['diff_dias'].mean().reset_index().dropna()
df_tempo_medio.columns = ['franqueado', 'tempo_medio_dias']
df_tempo_medio = df_tempo_medio.sort_values(by='tempo_medio_dias', ascending=False).head(15)
fig_tempo = px.bar(df_tempo_medio, y='franqueado', x='tempo_medio_dias', orientation='h',
                   title="Tempo Médio Entre Pedidos (em dias)")
fig_tempo.update_layout(yaxis_title="", xaxis_title="Dias", yaxis={'categoryorder':'total ascending'})
st.plotly_chart(fig_tempo, use_container_width=True)

# 📉 Queda de Pedidos
st.markdown("""<h4>📉 Franqueados com Tendência de Queda
<span class="tooltip"> ℹ️
  <span class="tooltiptext">
    Compara os dois últimos meses de pedidos por franqueado e mostra aqueles com queda superior a 10 pedidos. Exclui franqueados marcados como [Excluído].
  </span>
</span></h4>""", unsafe_allow_html=True)

df_trend = df_franqueados_ativos.groupby(['franqueado', 'ano_mes']).agg({'numero_pedido': 'count'}).reset_index()
df_trend = df_trend.sort_values(by=['franqueado', 'ano_mes'])
df_trend['delta'] = df_trend.groupby('franqueado')['numero_pedido'].diff()
df_last = df_trend.groupby('franqueado').tail(2)
df_last['mes_atual'] = df_last.groupby('franqueado')['numero_pedido'].shift(-1)
df_last['porcentagem'] = ((df_last['numero_pedido'] - df_last['mes_atual']) / df_last['numero_pedido']) * 100
df_queda = df_last.groupby('franqueado')['delta'].sum().reset_index()
df_queda.columns = ['franqueado', 'tendencia_queda']
df_queda = df_queda[df_queda['tendencia_queda'] < 0].sort_values(by='tendencia_queda')

# Alertas
st.markdown("### ⚠️ Alertas de Queda Relevante")
df_alertas = df_queda[
    (df_queda['tendencia_queda'] <= -10) &
    (~df_queda['franqueado'].str.contains(r'\[Excluído\]', case=False, na=False))
]
limite_alertas = 0
for i, row in df_alertas.head(limite_alertas).iterrows():
    st.warning(f"{row['franqueado']} teve uma queda de {abs(int(row['tendencia_queda']))} pedidos nos últimos meses.")
if len(df_alertas) > limite_alertas:
    with st.expander("Mostrar mais alertas"):
        for i, row in df_alertas.iloc[limite_alertas:].iterrows():
            st.warning(f"{row['franqueado']} teve uma queda de {abs(int(row['tendencia_queda']))} pedidos nos últimos meses.")
if df_alertas.empty:
    st.info("Nenhum franqueado teve queda superior a 10 pedidos nos últimos meses. 🎉")

# Gráfico de tendência de queda
df_queda_top10 = df_queda.head(10)
fig_queda = px.bar(df_queda_top10, x='franqueado', y='tendencia_queda',
                   title="Top 10 Franqueados com Maior Queda de Pedidos (últimos meses)")
fig_queda.update_layout(yaxis_title="Queda (nº de pedidos)", xaxis_title="", xaxis_tickangle=-45)
st.plotly_chart(fig_queda, use_container_width=True)
