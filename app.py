import streamlit as st
import pandas as pd
import plotly.express as px
import os

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Dashboard CEAP 2026", page_icon="🏛️", layout="wide", initial_sidebar_state="expanded")

# --- DICIONÁRIO GLOBAL DE MESES ---
MESES_MAP = {
    1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 
    5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto', 
    9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
}

# --- INJEÇÃO DE CSS (DARK MODE ELEGANTE & FONTES) ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Sora:wght@400;600;700&display=swap');
        
        html, body, [class*="css"] { font-family: 'Sora', sans-serif !important; }
        
        div[data-testid="stMetricValue"] {
            font-family: 'IBM Plex Mono', monospace !important;
            font-size: 1.8rem !important;
            color: #4DA8DA !important; 
        }
        
        div[data-testid="stMetricLabel"] {
            font-family: 'Sora', sans-serif !important;
            font-weight: 600 !important;
            color: #B0B0B0 !important;
        }
        
        div[data-testid="metric-container"] {
            background-color: #181818;
            padding: 1.2rem;
            border-radius: 12px;
            border: 1px solid #333333;
            box-shadow: 0 4px 6px rgba(0,0,0,0.4);
        }
        
        h1, h2, h3, h4 { color: #E0E0E0 !important; font-weight: 700 !important; }
    </style>
""", unsafe_allow_html=True)

st.title("🏛️ Dashboard Analítico - Cota Parlamentar 2026")
st.markdown("Análise interativa das despesas da Câmara dos Deputados (CEAP) utilizando cruzamento de dados.")

# --- FUNÇÃO PARA CARREGAR E TRATAR OS DADOS ---
def carregar_dados():
    caminho_gastos = os.path.join('dados', 'Ano-2026.csv')
    caminho_deputados = os.path.join('dados', 'deputados.csv')
    
    if not os.path.exists(caminho_gastos):
        st.error(f"Arquivo de gastos não encontrado em: {caminho_gastos}")
        return pd.DataFrame()

    df_gastos = pd.read_csv(caminho_gastos, sep=';', encoding='utf-8', low_memory=False)
    df_gastos.columns = df_gastos.columns.str.strip()
    
    if df_gastos['vlrLiquido'].dtype == 'object':
        df_gastos['vlrLiquido'] = df_gastos['vlrLiquido'].astype(str).str.replace(',', '.').astype(float)
        
    df_gastos = df_gastos[(df_gastos['vlrLiquido'] > 0) & (df_gastos['nuDeputadoId'].notna())]
    
    if 'numMes' in df_gastos.columns:
        df_gastos['MesNome'] = df_gastos['numMes'].map(MESES_MAP)
    else:
        df_gastos['MesNome'] = 'Desconhecido'
        df_gastos['numMes'] = 0

    if os.path.exists(caminho_deputados):
        df_deputados = pd.read_csv(caminho_deputados, sep=';', encoding='utf-8')
        df_deputados.columns = df_deputados.columns.str.strip()
        df_deputados['nuDeputadoId'] = df_deputados['uri'].astype(str).str.split('/').str[-1]
        
        df_gastos['nuDeputadoId'] = df_gastos['nuDeputadoId'].astype(int).astype(str)
        df_deputados['nuDeputadoId'] = df_deputados['nuDeputadoId'].astype(str)
        
        df_completo = pd.merge(
            df_gastos, 
            df_deputados[['nuDeputadoId', 'siglaSexo', 'ufNascimento']], 
            on='nuDeputadoId', 
            how='left'
        )
    else:
        st.warning(f"Arquivo biográfico não encontrado em '{caminho_deputados}'. Prosseguindo apenas com dados de consumo.")
        df_completo = df_gastos.copy()
        
    df_completo['sgPartido'] = df_completo['sgPartido'].fillna('Sem Partido')
    df_completo['sgUF'] = df_completo.get('sgUF', pd.Series(['ND']*len(df_completo))).fillna('ND')
    df_completo['txtDescricao'] = df_completo['txtDescricao'].fillna('Não Informado')
    
    return df_completo

# --- CARREGANDO OS DADOS ---
with st.spinner("Estruturando a base de dados..."):
    df = carregar_dados()

if df.empty:
    st.stop()

# COLUNA NOVA: Cria a string de exibição "Nome do Deputado (UF)"
df['Nome_Exibicao'] = df['txNomeParlamentar'] + " (" + df['sgUF'].astype(str) + ")"

# --- BARRA LATERAL (FILTROS) ---
st.sidebar.markdown("<h1 style='text-align: center; color: #4DA8DA;'>🏛️ CEAP</h1>", unsafe_allow_html=True)
st.sidebar.header("🔍 Filtros de Análise")

# LISTA DE OPÇÕES COM O NOME + ESTADO
lista_deputados = sorted(df['Nome_Exibicao'].dropna().unique())
nome_pesquisa = st.sidebar.selectbox(
    "Pesquisar por Nome do Deputado", 
    options=lista_deputados,
    index=None,
    placeholder="Digite para buscar..."
)

estado_selecionado = st.sidebar.multiselect("Estado (UF)", sorted(df['sgUF'].unique()))
partido_selecionado = st.sidebar.multiselect("Partido Político", sorted(df['sgPartido'].unique()))

meses_disponiveis = sorted(df['numMes'].unique())
meses_nomes_disponiveis = [MESES_MAP[k] for k in meses_disponiveis if k in MESES_MAP]
mes_selecionado = st.sidebar.multiselect("Mês", meses_nomes_disponiveis)

tipo_despesa_selecionado = st.sidebar.multiselect("Tipo de Despesa", sorted(df['txtDescricao'].unique()))

st.sidebar.markdown("---")
top_n = st.sidebar.slider("Exibir Top N Deputados no Ranking", min_value=5, max_value=50, value=15, step=5)

# --- APLICANDO OS FILTROS ---
df_filtrado = df.copy()

# FILTRANDO PELA NOVA COLUNA DE EXIBIÇÃO
if nome_pesquisa:
    df_filtrado = df_filtrado[df_filtrado['Nome_Exibicao'] == nome_pesquisa]
if estado_selecionado:
    df_filtrado = df_filtrado[df_filtrado['sgUF'].isin(estado_selecionado)]
if partido_selecionado:
    df_filtrado = df_filtrado[df_filtrado['sgPartido'].isin(partido_selecionado)]
if mes_selecionado:
    df_filtrado = df_filtrado[df_filtrado['MesNome'].isin(mes_selecionado)]
if tipo_despesa_selecionado:
    df_filtrado = df_filtrado[df_filtrado['txtDescricao'].isin(tipo_despesa_selecionado)]

# --- MÉTRICAS GERAIS (KPIs) ---
total_gasto = df_filtrado['vlrLiquido'].sum()
qtd_deputados = df_filtrado['txNomeParlamentar'].nunique()
qtd_lancamentos = len(df_filtrado)
media_por_dep = total_gasto / qtd_deputados if qtd_deputados > 0 else 0

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Gasto", f"R$ {total_gasto/1e6:,.2f} M".replace(',', 'X').replace('.', ',').replace('X', '.'))
with col2:
    st.metric("Deputados", f"{qtd_deputados:,}".replace(',', '.'))
with col3:
    st.metric("Lançamentos", f"{qtd_lancamentos:,}".replace(',', '.'))
with col4:
    st.metric("Média por Dep.", f"R$ {media_por_dep:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))

st.markdown("<br>", unsafe_allow_html=True)

template_grafico = "plotly_dark"
cores_grafico = px.colors.qualitative.Pastel

# --- BLOCO 1: RANKING MAIORES GASTADORES ---
st.markdown(f"### 🏆 Top {top_n} Maiores Gastadores")
df_ranking = df_filtrado.groupby(['txNomeParlamentar', 'sgUF', 'sgPartido']).agg(
    vlrLiquido=('vlrLiquido', 'sum'),
    lancamentos=('vlrLiquido', 'count')
).reset_index().sort_values(by='vlrLiquido', ascending=False).head(top_n)

fig_ranking = px.bar(
    df_ranking, 
    x='vlrLiquido', 
    y='txNomeParlamentar',
    orientation='h',
    hover_data={'txNomeParlamentar': False, 'sgUF': True, 'sgPartido': True, 'lancamentos': True, 'vlrLiquido': ':,.2f'},
    labels={'vlrLiquido': 'Total Gasto (R$)', 'txNomeParlamentar': 'Deputado', 'sgUF': 'UF', 'sgPartido': 'Partido', 'lancamentos': 'Qtd. Lançamentos'},
    template=template_grafico,
    color='vlrLiquido',
    color_continuous_scale='Blues'
)
fig_ranking.update_layout(yaxis={'categoryorder':'total ascending'}, showlegend=False, margin=dict(l=0, r=0, t=10, b=0))
st.plotly_chart(fig_ranking, use_container_width=True)

# --- BLOCO 2: ANÁLISE PARTIDÁRIA E GEOGRÁFICA ---
col_graf1, col_graf2 = st.columns(2)

with col_graf1:
    st.markdown("#### 🏢 Top 15 Partidos")
    df_partido = df_filtrado.groupby('sgPartido')['vlrLiquido'].sum().reset_index().sort_values('vlrLiquido', ascending=False).head(15)
    fig_partido = px.bar(
        df_partido, x='sgPartido', y='vlrLiquido',
        labels={'vlrLiquido': 'Valor Total (R$)', 'sgPartido': 'Partido'},
        template=template_grafico, color_discrete_sequence=['#4DA8DA']
    )
    fig_partido.update_layout(xaxis={'categoryorder':'total descending'}, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig_partido, use_container_width=True)

with col_graf2:
    st.markdown("#### 🗺️ Gastos por Estado (UF)")
    df_uf = df_filtrado.groupby('sgUF')['vlrLiquido'].sum().reset_index().sort_values('vlrLiquido', ascending=False)
    fig_uf = px.bar(
        df_uf, x='sgUF', y='vlrLiquido',
        labels={'vlrLiquido': 'Valor Total (R$)', 'sgUF': 'Estado'},
        template=template_grafico, color_discrete_sequence=['#82CFFD']
    )
    fig_uf.update_layout(xaxis={'categoryorder':'total descending'}, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig_uf, use_container_width=True)

# --- BLOCO 3: EVOLUÇÃO MENSAL ---
st.markdown("### 📈 Evolução Mensal dos Gastos")
df_mensal = df_filtrado.groupby(['numMes', 'MesNome'])['vlrLiquido'].sum().reset_index().sort_values('numMes')
fig_evolucao = px.area(
    df_mensal, x='MesNome', y='vlrLiquido',
    labels={'vlrLiquido': 'Valor Gasto (R$)', 'MesNome': 'Mês'},
    template=template_grafico, color_discrete_sequence=['#4DA8DA'],
    markers=True
)
fig_evolucao.update_layout(xaxis={'categoryorder':'array', 'categoryarray': list(MESES_MAP.values())}, margin=dict(l=0, r=0, t=10, b=0))
st.plotly_chart(fig_evolucao, use_container_width=True)

# --- BLOCO 4: CATEGORIAS DE DESPESA ---
col_graf3, col_graf4 = st.columns(2)

with col_graf3:
    st.markdown("#### 🛒 Top 12 Tipos de Despesa")
    df_cat = df_filtrado.groupby('txtDescricao')['vlrLiquido'].sum().reset_index().sort_values('vlrLiquido', ascending=False)
    fig_cat = px.bar(
        df_cat.head(12), x='vlrLiquido', y='txtDescricao', orientation='h',
        labels={'vlrLiquido': 'Valor Total (R$)', 'txtDescricao': 'Categoria'},
        template=template_grafico, color_discrete_sequence=['#4DA8DA']
    )
    fig_cat.update_layout(yaxis={'categoryorder':'total ascending'}, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig_cat, use_container_width=True)

with col_graf4:
    st.markdown("#### 🍩 Distribuição de Gastos")
    top_8_cat = df_cat.head(8)
    outros_valor = df_cat.iloc[8:]['vlrLiquido'].sum()
    
    if outros_valor > 0:
        df_outros = pd.DataFrame({'txtDescricao': ['Outros'], 'vlrLiquido': [outros_valor]})
        df_donut = pd.concat([top_8_cat, df_outros], ignore_index=True)
    else:
        df_donut = top_8_cat

    fig_donut = px.pie(
        df_donut, values='vlrLiquido', names='txtDescricao', hole=0.5,
        template=template_grafico, color_discrete_sequence=cores_grafico
    )
    fig_donut.update_layout(margin=dict(l=0, r=0, t=10, b=0), legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(fig_donut, use_container_width=True)

st.divider()

# --- TABELA DE DADOS E EXPORTAÇÃO ---
st.markdown("### 📋 Tabela de Dados Consolidada")

df_tabela = df_filtrado.groupby(['txNomeParlamentar', 'sgUF', 'sgPartido']).agg(
    Total_Gasto=('vlrLiquido', 'sum'),
    Lancamentos=('vlrLiquido', 'count')
).reset_index()

df_tabela['Ticket_Medio'] = df_tabela['Total_Gasto'] / df_tabela['Lancamentos']
df_tabela = df_tabela.sort_values('Total_Gasto', ascending=False)

df_tabela.rename(columns={
    'txNomeParlamentar': 'Deputado',
    'sgUF': 'UF',
    'sgPartido': 'Partido',
    'Total_Gasto': 'Total Gasto (R$)',
    'Lancamentos': 'Lançamentos',
    'Ticket_Medio': 'Ticket Médio (R$)'
}, inplace=True)

st.dataframe(
    df_tabela.style.format({
        'Total Gasto (R$)': 'R$ {:,.2f}',
        'Ticket Médio (R$)': 'R$ {:,.2f}'
    }), 
    use_container_width=True,
    hide_index=True,
    height=350
)

csv = df_tabela.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
st.download_button(
    label="⬇️ Baixar Tabela em CSV",
    data=csv,
    file_name='ranking_deputados_ceap_2026.csv',
    mime='text/csv',
)