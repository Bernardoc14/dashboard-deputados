import streamlit as st
import pandas as pd
import plotly.express as px
import os

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Dashboard Legislativo 2026", 
    page_icon="🏛️", 
    layout="wide"
)

# Estilo visual
template_grafico = "plotly_white"
cores_grafico = px.colors.qualitative.Prism

# --- 1. CARREGAMENTO DE DADOS ---
@st.cache_data
def carregar_dados():
    caminho_gastos = os.path.join('dados', 'Ano-2026.csv')
    caminho_deputados = os.path.join('dados', 'deputados_detalhado.csv')
    
    df_gastos = pd.read_csv(caminho_gastos, sep=';', encoding='utf-8')
    df_deputados = pd.read_csv(caminho_deputados, sep=';', encoding='utf-8')
    
    # Padronização de IDs para o Join
    df_gastos['id_oficial'] = pd.to_numeric(df_gastos['ideCadastro'], errors='coerce')
    df_deputados['id_oficial'] = df_deputados['uri'].str.split('/').str[-1].str.strip()
    df_deputados['id_oficial'] = pd.to_numeric(df_deputados['id_oficial'], errors='coerce')
    
    df_merge = pd.merge(
        df_gastos, 
        df_deputados[['id_oficial', 'siglaSexo', 'ufNascimento', 'escolaridade']], 
        on='id_oficial', 
        how='left'
    )
    df_merge['escolaridade'] = df_merge['escolaridade'].fillna('Não Informado')
    return df_merge

df_principal = carregar_dados()

# --- 2. FILTROS LATERAIS ---
st.sidebar.header("🔍 Filtros Globais")
nome_busca = st.sidebar.text_input("Buscar por Nome")

partidos = sorted(df_principal['sgPartido'].dropna().unique())
partido_sel = st.sidebar.multiselect("Partidos", partidos)

ufs = sorted(df_principal['sgUF'].dropna().unique())
uf_sel = st.sidebar.multiselect("Estados (UF)", ufs)

df_filtrado = df_principal.copy()
if nome_busca:
    df_filtrado = df_filtrado[df_filtrado['txNomeParlamentar'].str.contains(nome_busca, case=False, na=False)]
if partido_sel:
    df_filtrado = df_filtrado[df_filtrado['sgPartido'].isin(partido_sel)]
if uf_sel:
    df_filtrado = df_filtrado[df_filtrado['sgUF'].isin(uf_sel)]

# --- 3. MÉTRICAS ---
st.title("🏛️ Dashboard Legislativo 2026")
m1, m2, m3 = st.columns(3)
m1.metric("Gasto Total", f"R$ {df_filtrado['vlrLiquido'].sum():,.2f}")
m2.metric("Deputados Selecionados", df_filtrado['txNomeParlamentar'].nunique())
m3.metric("Notas Fiscais", f"{len(df_filtrado):,}")

st.divider()

# --- 4. SEÇÃO P1 (RANKING DE GASTOS) ---
st.header("💰 P1 — Ranking de Gastos por Deputado")

# Slider agora ocupa a largura total ou pode ser colocado em uma coluna menor para não ficar gigante
col_slider, _ = st.columns([0.4, 0.6])
with col_slider:
    n_top = st.slider("Mostrar quantos deputados no ranking?", 5, 50, 15)

ranking_data = df_filtrado.groupby(['txNomeParlamentar', 'sgPartido', 'sgUF'])['vlrLiquido'].sum().sort_values(ascending=False).reset_index()

fig_p1 = px.bar(
    ranking_data.head(n_top), x='vlrLiquido', y='txNomeParlamentar',
    orientation='h', color='vlrLiquido', color_continuous_scale='Reds',
    template=template_grafico, hover_data=['sgPartido', 'sgUF']
)
fig_p1.update_layout(yaxis={'categoryorder':'total ascending'}, height=400 + (n_top * 10)) # Altura dinâmica
st.plotly_chart(fig_p1, use_container_width=True)

with st.expander("📊 Ver Tabela de Ranking Completa"):
    st.dataframe(ranking_data, use_container_width=True, hide_index=True)

st.divider()

# --- 5. SEÇÃO P13 (TIPOS DE DESPESA) ---
st.header("📑 P13 — Tipos de Despesa")

# Usando colunas apenas para centralizar o gráfico de pizza (evita que ele fique oval e gigante)
col_vazia_l, col_conteudo_p13, col_vazia_r = st.columns([0.2, 0.6, 0.2])

with col_conteudo_p13:
    tab_global, tab_individual = st.tabs(["🌎 Visão Geral (Todos)", "👤 Visão por Deputado"])
    
    with tab_global:
        cat_data = df_filtrado.groupby('txtDescricao')['vlrLiquido'].sum().reset_index()
        fig_global = px.pie(cat_data, values='vlrLiquido', names='txtDescricao', hole=0.4)
        fig_global.update_layout(showlegend=True) # Ativei a legenda aqui pois há mais espaço agora
        st.plotly_chart(fig_global, use_container_width=True)

    with tab_individual:
        lista_nomes = sorted(df_filtrado['txNomeParlamentar'].unique())
        if len(lista_nomes) > 0:
            dep_escolhido = st.selectbox("Selecione um deputado para análise individual:", lista_nomes)
            df_ind = df_filtrado[df_filtrado['txNomeParlamentar'] == dep_escolhido]
            cat_ind = df_ind.groupby('txtDescricao')['vlrLiquido'].sum().reset_index()
            
            fig_ind = px.pie(cat_ind, values='vlrLiquido', names='txtDescricao', hole=0.4,
                            color_discrete_sequence=px.colors.qualitative.Safe)
            st.plotly_chart(fig_ind, use_container_width=True)
            st.info(f"Total gasto por {dep_escolhido}: R$ {df_ind['vlrLiquido'].sum():,.2f}")
        else:
            st.warning("Nenhum deputado encontrado.")

st.divider()

# --- 6. SEÇÃO P4 (ESCOLARIDADE) ---
st.header("🎓 P4 — Perfil por Escolaridade")
df_u = df_filtrado.drop_duplicates(subset=['txNomeParlamentar'])
esc_data = df_u['escolaridade'].value_counts().reset_index()
esc_data.columns = ['Escolaridade', 'Qtd']

fig_p4 = px.bar(esc_data, x='Qtd', y='Escolaridade', orientation='h',
                color='Qtd', color_continuous_scale='Blues', text_auto=True)
fig_p4.update_layout(yaxis={'categoryorder':'total ascending'})
st.plotly_chart(fig_p4, use_container_width=True)

st.divider()

# --- 7. DADOS BRUTOS ---
with st.expander("📋 Detalhamento de Notas Fiscais"):
    st.dataframe(df_filtrado[['txNomeParlamentar', 'sgPartido', 'txtDescricao', 'vlrLiquido', 'escolaridade']], use_container_width=True)

st.markdown(f"*Dados processados pelo Grupo 6 - BDR 2026*")