import streamlit as st
import pandas as pd
import plotly.express as px
import os
import glob
import csv
from wordcloud import WordCloud
import matplotlib.pyplot as plt

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Dashboard Legislativo 2023-2026", page_icon="🏛️", layout="wide")
template_grafico = "plotly_white"

@st.cache_data
def carregar_tudo():
    # A. GASTOS + PERFIL (P1, P4, P13)
    arquivos_gastos = glob.glob(os.path.join('dados', 'Ano-*.csv'))
    df_gastos = pd.concat([pd.read_csv(f, sep=';', encoding='utf-8') for f in arquivos_gastos], ignore_index=True)
    df_gastos['id_oficial'] = pd.to_numeric(df_gastos['ideCadastro'], errors='coerce')
    
    df_dep = pd.read_csv(os.path.join('dados', 'deputados_detalhado.csv'), sep=';', encoding='utf-8')
    df_dep['id_oficial'] = df_dep['uri'].str.split('/').str[-1].str.strip().apply(pd.to_numeric, errors='coerce')
    
    df_principal = pd.merge(df_gastos, df_dep[['id_oficial', 'siglaSexo', 'escolaridade']], on='id_oficial', how='left')
    df_principal['escolaridade'] = df_principal['escolaridade'].fillna('Não Informado')
    
    # B. FREQUÊNCIA (P11a)
    arquivos_presenca = glob.glob(os.path.join('dados', 'eventosPresencaDeputados-*.csv'))
    if arquivos_presenca:
        df_pres = pd.concat([pd.read_csv(f, sep=';', encoding='utf-8') for f in arquivos_presenca], ignore_index=True)
        df_pres['id_oficial'] = pd.to_numeric(df_pres['idDeputado'], errors='coerce')
        total_eventos = df_pres['idEvento'].nunique()
        presencas_por_deputado = df_pres.groupby('id_oficial').size() / total_eventos * 100
        mapeamento_partido = df_principal[['id_oficial', 'sgPartido']].drop_duplicates()
        df_freq_dep = presencas_por_deputado.reset_index(name='perc_frequencia')
        df_freq_final = pd.merge(df_freq_dep, mapeamento_partido, on='id_oficial')
        frequencia_partido = df_freq_final.groupby('sgPartido')['perc_frequencia'].mean()
    else:
        frequencia_partido = pd.Series()
    
    # C. PRODUÇÃO (P11b)
    arquivos_autores = glob.glob(os.path.join('dados', 'proposicoesAutores-*.csv'))
    df_autores = pd.concat([pd.read_csv(f, sep=';', encoding='utf-8') for f in arquivos_autores], ignore_index=True)
    df_autores['id_oficial'] = pd.to_numeric(df_autores['idDeputadoAutor'], errors='coerce')
    
    # D. EMENTAS PARA NUVEM (P11d) - COM FIX PARA BUFFER OVERFLOW
    arquivos_prop = glob.glob(os.path.join('dados', 'proposicoes-*.csv'))
    lista_prop = []
    for f in arquivos_prop:
        try:
            df_temp = pd.read_csv(f, sep=';', encoding='utf-8', on_bad_lines='skip', quoting=csv.QUOTE_NONE, engine='python')
            lista_prop.append(df_temp)
        except Exception as e:
            print(f"Erro ao tentar ler o arquivo {f}: {e}")
            
    if lista_prop:
        df_prop = pd.concat(lista_prop, ignore_index=True)
        col_ementa = next((col for col in df_prop.columns if 'ementa' in col.lower()), None)
        col_id = 'id' if 'id' in df_prop.columns else next((col for col in df_prop.columns if 'idproposicao' in col.lower() or 'id_proposicao' in col.lower()), None)
        
        if col_ementa and col_id:
            df_prop['ementa'] = df_prop[col_ementa].astype(str).str.replace('"', '')
            df_autores['idProposicao'] = df_autores['idProposicao'].astype(str)
            df_prop[col_id] = df_prop[col_id].astype(str)
            df_temas = pd.merge(df_autores[['idProposicao', 'id_oficial']], df_prop[[col_id, 'ementa']], left_on='idProposicao', right_on=col_id)
        else:
            df_temas = pd.DataFrame(columns=['idProposicao', 'id_oficial', 'ementa'])
    else:
        df_temas = pd.DataFrame(columns=['idProposicao', 'id_oficial', 'ementa'])

    return df_principal, frequencia_partido, df_autores, df_temas

# --- EXECUÇÃO DO CARREGAMENTO ---
df_principal, df_freq, df_autores, df_temas = carregar_tudo()

# --- FILTROS LATERAIS ---
st.sidebar.header("🔍 Filtros Globais")
nome_busca = st.sidebar.text_input("Buscar por Nome")
partidos_disp = sorted(df_principal['sgPartido'].dropna().unique())
partido_sel = st.sidebar.multiselect("Partidos", partidos_disp)
ufs_disp = sorted(df_principal['sgUF'].dropna().unique())
uf_sel = st.sidebar.multiselect("Estados (UF)", ufs_disp)

df_filtrado = df_principal.copy()
if nome_busca:
    df_filtrado = df_filtrado[df_filtrado['txNomeParlamentar'].str.contains(nome_busca, case=False, na=False)]
if partido_sel:
    df_filtrado = df_filtrado[df_filtrado['sgPartido'].isin(partido_sel)]
if uf_sel:
    df_filtrado = df_filtrado[df_filtrado['sgUF'].isin(uf_sel)]

# --- MÉTRICAS GLOBAIS ---
st.title("🏛️ Dashboard Legislativo 2023-2026")
m1, m2, m3 = st.columns(3)
m1.metric("Gasto Total Acumulado", f"R$ {df_filtrado['vlrLiquido'].sum():,.2f}")
m2.metric("Deputados Analisados", df_filtrado['txNomeParlamentar'].nunique())
m3.metric("Notas Fiscais Processadas", f"{len(df_filtrado):,}")
st.divider()

# --- SEÇÃO P1 (RANKING DE GASTOS) ---
st.header("💰 P1 — Ranking de Gastos por Deputado")
col_slider, _ = st.columns([0.4, 0.6])
with col_slider:
    n_top = st.slider("Mostrar quantos deputados no ranking?", 5, 50, 15)

ranking_data = df_filtrado.groupby(['txNomeParlamentar', 'sgPartido', 'sgUF'])['vlrLiquido'].sum().sort_values(ascending=False).reset_index()
fig_p1 = px.bar(
    ranking_data.head(n_top), x='vlrLiquido', y='txNomeParlamentar',
    orientation='h', color='vlrLiquido', color_continuous_scale='Reds',
    template=template_grafico, hover_data=['sgPartido', 'sgUF']
)
fig_p1.update_layout(yaxis={'categoryorder':'total ascending'}, height=400 + (n_top * 10))
st.plotly_chart(fig_p1, use_container_width=True)
st.divider()

# --- SEÇÃO P11 (RANKING DE PARTIDOS) ---
st.header("📊 P11 — Ranking de Partidos")

# Recalculando os dados dos partidos respeitando os filtros (se houver)
df_partidos = df_filtrado.groupby('sgPartido').agg({'vlrLiquido': 'sum'}).reset_index()
df_partidos['perc_frequencia'] = df_partidos['sgPartido'].map(df_freq).fillna(0)

df_link_partido = df_filtrado[['id_oficial', 'sgPartido']].drop_duplicates()
df_prod_partido = pd.merge(df_autores, df_link_partido, on='id_oficial')
contagem_prod = df_prod_partido.groupby('sgPartido').size()
df_partidos['qtd_proposicoes'] = df_partidos['sgPartido'].map(contagem_prod).fillna(0)

tab_a, tab_b, tab_c, tab_d = st.tabs(["a) Frequência (%)", "b) Proposições", "c) Gastos Totais", "d) Nuvem de Temas"])

with tab_a:
    fig_a = px.bar(df_partidos.sort_values('perc_frequencia', ascending=False), x='sgPartido', y='perc_frequencia', color='perc_frequencia', color_continuous_scale='Viridis', template=template_grafico)
    st.plotly_chart(fig_a, use_container_width=True)

with tab_b:
    fig_b = px.bar(df_partidos.sort_values('qtd_proposicoes', ascending=False), x='sgPartido', y='qtd_proposicoes', color='qtd_proposicoes', color_continuous_scale='Greens', template=template_grafico)
    st.plotly_chart(fig_b, use_container_width=True)

with tab_c:
    fig_c = px.bar(df_partidos.sort_values('vlrLiquido', ascending=False), x='sgPartido', y='vlrLiquido', color='vlrLiquido', color_continuous_scale='Reds', template=template_grafico)
    st.plotly_chart(fig_c, use_container_width=True)

with tab_d:
    if not df_partidos.empty:
        partido_n = st.selectbox("Selecione o Partido para a Nuvem de Palavras:", df_partidos['sgPartido'].unique())
        ids_dep = df_link_partido[df_link_partido['sgPartido'] == partido_n]['id_oficial']
        ementas_partido = df_temas[df_temas['id_oficial'].isin(ids_dep)]['ementa'].dropna()
        texto = " ".join(ementas_partido)
        
        if len(texto) > 10:
            wc = WordCloud(width=800, height=400, background_color='white', colormap='tab10').generate(texto)
            fig_d, ax = plt.subplots()
            ax.imshow(wc, interpolation='bilinear')
            ax.axis('off')
            st.pyplot(fig_d)
        else:
            st.warning("Pouco texto disponível para gerar a nuvem deste partido.")
st.divider()

# --- SEÇÃO P13 (TIPOS DE DESPESA) ---
st.header("📑 P13 — Tipos de Despesa")
col_vazia_l, col_conteudo_p13, col_vazia_r = st.columns([0.2, 0.6, 0.2])

with col_conteudo_p13:
    tab_global, tab_individual = st.tabs(["🌎 Visão Geral (Todos)", "👤 Visão por Deputado"])
    with tab_global:
        cat_data = df_filtrado.groupby('txtDescricao')['vlrLiquido'].sum().reset_index()
        fig_global = px.pie(cat_data, values='vlrLiquido', names='txtDescricao', hole=0.4, template=template_grafico)
        st.plotly_chart(fig_global, use_container_width=True)

    with tab_individual:
        lista_nomes = sorted(df_filtrado['txNomeParlamentar'].dropna().unique())
        if len(lista_nomes) > 0:
            dep_escolhido = st.selectbox("Selecione um deputado para análise individual:", lista_nomes)
            df_ind = df_filtrado[df_filtrado['txNomeParlamentar'] == dep_escolhido]
            cat_ind = df_ind.groupby('txtDescricao')['vlrLiquido'].sum().reset_index()
            
            fig_ind = px.pie(cat_ind, values='vlrLiquido', names='txtDescricao', hole=0.4, color_discrete_sequence=px.colors.qualitative.Safe)
            st.plotly_chart(fig_ind, use_container_width=True)
            st.info(f"Total gasto por {dep_escolhido}: R$ {df_ind['vlrLiquido'].sum():,.2f}")

st.divider()

# --- SEÇÃO P4 (ESCOLARIDADE) ---
st.header("🎓 P4 — Perfil por Escolaridade")
df_u = df_filtrado.drop_duplicates(subset=['id_oficial'])
esc_data = df_u['escolaridade'].value_counts().reset_index()
esc_data.columns = ['Escolaridade', 'Qtd']

fig_p4 = px.bar(esc_data, x='Qtd', y='Escolaridade', orientation='h', color='Qtd', color_continuous_scale='Blues', text_auto=True, template=template_grafico)
fig_p4.update_layout(yaxis={'categoryorder':'total ascending'})
st.plotly_chart(fig_p4, use_container_width=True)