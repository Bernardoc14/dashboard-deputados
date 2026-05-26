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

# --- 1. FUNÇÕES DE CARREGAMENTO DE DADOS (COM CACHE) ---

@st.cache_data
def carregar_tudo():
    # A. GASTOS + PERFIL (P1, P4, P13)
    arquivos_gastos = glob.glob(os.path.join('dados', 'Ano-*.csv'))
    # low_memory=False ajuda com arquivos grandes e tipos de dados mistos
    df_gastos = pd.concat([pd.read_csv(f, sep=';', encoding='utf-8', low_memory=False) for f in arquivos_gastos], ignore_index=True)
    
    # PADRONIZAÇÃO CRÍTICA DE IDs: Transforma ideCadastro em texto limpo (sem .0)
    df_gastos['id_oficial'] = df_gastos['ideCadastro'].astype(str).str.split('.').str[0].str.strip()
    
    df_dep = pd.read_csv(os.path.join('dados', 'deputados_detalhado.csv'), sep=';', encoding='utf-8')
    # Padroniza o ID extraído da URL do deputado
    df_dep['id_oficial'] = df_dep['uri'].str.split('/').str[-1].str.strip().astype(str).str.split('.').str[0]
    
    df_principal = pd.merge(df_gastos, df_dep[['id_oficial', 'siglaSexo', 'escolaridade']], on='id_oficial', how='left')
    df_principal['escolaridade'] = df_principal['escolaridade'].fillna('Não Informado')
    
    # B. FREQUÊNCIA (P11a)
    arquivos_presenca = glob.glob(os.path.join('dados', 'eventosPresencaDeputados-*.csv'))
    if arquivos_presenca:
        df_pres = pd.concat([pd.read_csv(f, sep=';', encoding='utf-8') for f in arquivos_presenca], ignore_index=True)
        # Padroniza idDeputado
        df_pres['id_oficial'] = df_pres['idDeputado'].astype(str).str.split('.').str[0].str.strip()
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
    if arquivos_autores:
        df_autores = pd.concat([pd.read_csv(f, sep=';', encoding='utf-8') for f in arquivos_autores], ignore_index=True)
        # Remove autores sem ID de deputado (ex: Senadores, Órgãos)
        df_autores = df_autores[df_autores['idDeputadoAutor'].notna() & (df_autores['idDeputadoAutor'].astype(str).str.strip() != '')]
        # Padroniza idDeputadoAutor
        df_autores['id_oficial'] = df_autores['idDeputadoAutor'].astype(str).str.split('.').str[0].str.strip()
        df_autores['idProposicao_link'] = df_autores['idProposicao'].astype(str).str.split('.').str[0].str.strip()
    else:
        df_autores = pd.DataFrame(columns=['id_oficial', 'idProposicao_link'])
    
    # D. EMENTAS PARA NUVEM (P11d)
    arquivos_prop = glob.glob(os.path.join('dados', 'proposicoes-*.csv'))
    lista_prop = []
    for f in arquivos_prop:
        try:
            # engine='python' com on_bad_lines='skip' trata ementas com quebra de linha
            df_temp = pd.read_csv(f, sep=';', encoding='utf-8', on_bad_lines='skip', engine='python')
            lista_prop.append(df_temp)
        except Exception as e:
            print(f"Erro ao tentar ler o arquivo de proposições {f}: {e}")
            
    if lista_prop:
        df_prop = pd.concat(lista_prop, ignore_index=True)
        
        # Busca flexível por colunas de Ementa e ID
        col_ementa = next((col for col in df_prop.columns if 'ementa' in col.lower()), None)
        col_id = next((col for col in df_prop.columns if col.lower() in ['id', 'idproposicao', 'id_proposicao']), None)
        
        if col_ementa and col_id:
            df_prop['ementa'] = df_prop[col_ementa].astype(str).str.replace('"', '')
            # Padroniza ID da proposição
            df_prop['idProposicao_link'] = df_prop[col_id].astype(str).str.split('.').str[0].str.strip()
            # Merge robusco usando strings padronizadas
            df_temas = pd.merge(df_autores[['idProposicao_link', 'id_oficial']], df_prop[['idProposicao_link', 'ementa']], on='idProposicao_link', how='inner')
        else:
            df_temas = pd.DataFrame(columns=['idProposicao_link', 'id_oficial', 'ementa'])
    else:
        df_temas = pd.DataFrame(columns=['idProposicao_link', 'id_oficial', 'ementa'])

    # E. CLASSIFICAÇÃO TEMÁTICA (P3) — classifica proposições por eixo temático
    TEMAS_KEYWORDS = {
        'Saúde':          ['saúde', 'médic', 'hospital', 'sus', 'doença', 'farmac', 'vacin', 'enferm', 'sanitár', 'anvisa', 'medicamento'],
        'Educação':       ['educaç', 'escola', 'ensino', 'universidade', 'professor', 'aluno', 'magistério', 'bolsa', 'enem', 'fundeb', 'creche'],
        'Segurança':      ['segurança', 'polici', 'crime', 'pena', 'presídio', 'violência', 'penal', 'armamento', 'arma', 'tráfico'],
        'Tributário':     ['tribut', 'imposto', 'taxa', 'fiscal', 'icms', 'iss', 'irpf', 'receita federal', 'alíquota', 'contribuição'],
        'Econômico':      ['econom', 'indústria', 'comercio', 'empresa', 'empreend', 'crédito', 'banco', 'financ', 'mercado', 'investimento'],
        'Ambiental':      ['ambient', 'floresta', 'desmatamento', 'clima', 'carbono', 'sustentáv', 'poluiç', 'resíduo', 'biodiversidade'],
        'Infraestrutura': ['infraestrutura', 'rodovia', 'ferrovia', 'porto', 'aeroporto', 'saneamento', 'habitação', 'obras', 'energia elétrica'],
        'Social':         ['social', 'família', 'criança', 'idoso', 'mulher', 'pessoa com deficiência', 'vulneráv', 'pobreza', 'bolsa família'],
        'Agropecuário':   ['agrícol', 'agropec', 'rural', 'agricultor', 'pecuári', 'soja', 'agroneg'],
    }

    def classificar_tema(row):
        texto = (str(row.get('ementa', ''))).lower()
        scores = {tema: sum(1 for p in palavras if p in texto) for tema, palavras in TEMAS_KEYWORDS.items()}
        scores = {k: v for k, v in scores.items() if v > 0}
        return max(scores, key=scores.get) if scores else None

    if not df_temas.empty:
        df_temas['tema'] = df_temas.apply(classificar_tema, axis=1)
        df_temas_classificado = df_temas.dropna(subset=['tema'])
    else:
        df_temas_classificado = pd.DataFrame(columns=['idProposicao_link', 'id_oficial', 'ementa', 'tema'])

    # F. VOTOS POR TEMA (P3) — cruza votos dos deputados com proposições classificadas
    arquivos_votacoes = glob.glob(os.path.join('dados', 'votacoes-*.csv'))
    if arquivos_votacoes:
        df_votacoes_p3 = pd.concat(
            [pd.read_csv(f, sep=';', encoding='utf-8', on_bad_lines='skip', engine='python') for f in arquivos_votacoes],
            ignore_index=True
        )
    else:
        df_votacoes_p3 = pd.DataFrame(columns=['id', 'ultimaApresentacaoProposicao_idProposicao'])

    arquivos_votos_p3 = glob.glob(os.path.join('dados', 'votacoesVotos-*.csv'))
    if arquivos_votos_p3:
        df_votos_p3 = pd.concat(
            [pd.read_csv(f, sep=';', encoding='utf-8', low_memory=False) for f in arquivos_votos_p3],
            ignore_index=True
        )
    else:
        df_votos_p3 = pd.DataFrame(columns=['idVotacao', 'deputado_id', 'voto'])

    if not df_votos_p3.empty and not df_temas_classificado.empty:
        df_votos_p3['id_oficial'] = df_votos_p3['deputado_id'].astype(str).str.split('.').str[0].str.strip()
        df_votacoes_p3['idProposicao_link'] = df_votacoes_p3['ultimaApresentacaoProposicao_idProposicao'].astype(str).str.split('.').str[0].str.strip()
        df_votos_detalhado = pd.merge(df_votos_p3, df_votacoes_p3[['id', 'idProposicao_link']], left_on='idVotacao', right_on='id', how='left')
        df_votos_temas = pd.merge(df_votos_detalhado, df_temas_classificado[['idProposicao_link', 'tema', 'ementa']], on='idProposicao_link', how='inner')
    else:
        df_votos_temas = pd.DataFrame(columns=['id_oficial', 'tema', 'voto', 'ementa'])

    return df_principal, frequencia_partido, df_autores, df_temas, df_temas_classificado, df_votos_temas, TEMAS_KEYWORDS

@st.cache_data
def carregar_votos_e_calcular_alinhamento(df_principal_completo):
    # E. VOTOS (P10)
    arquivos_votos = glob.glob(os.path.join('dados', 'votacoesVotos-*.csv'))
    vazio = (
        pd.DataFrame(columns=['sgPartido', 'perc_alinhamento']),
        pd.DataFrame(),
        pd.DataFrame(),
        '',
        ''
    )

    if not arquivos_votos:
        return vazio

    try:
        lista_votos = [pd.read_csv(f, sep=';', encoding='utf-8', low_memory=False) for f in arquivos_votos]
        df_votos = pd.concat(lista_votos, ignore_index=True)

        # 1. Padronizar IDs para o cruzamento
        if 'idDeputado' in df_votos.columns:
            id_col_votos = 'idDeputado'
        elif 'deputado_id' in df_votos.columns:
            id_col_votos = 'deputado_id'
        else:
            id_col_votos = next((col for col in df_votos.columns if 'deputado' in col.lower() and 'id' in col.lower()), None)
        if not id_col_votos: return vazio
        df_votos['id_oficial'] = df_votos[id_col_votos].astype(str).str.split('.').str[0].str.strip()

        # 2. Mapeamento Deputado -> Partido
        mapeamento_partido = df_principal_completo[['id_oficial', 'sgPartido']].drop_duplicates()
        df_votos_partido = pd.merge(df_votos, mapeamento_partido, on='id_oficial', how='inner')

        # 3. Filtrar votos válidos (Sim ou Não)
        if 'tipoVoto' in df_votos.columns:
            voto_col = 'tipoVoto'
        elif 'voto' in df_votos.columns:
            voto_col = 'voto'
        else:
            voto_col = next((col for col in df_votos.columns if 'voto' in col.lower() or 'decisao' in col.lower()), None)
        if not voto_col: return vazio
        df_votos_validos = df_votos_partido[df_votos_partido[voto_col].isin(['Sim', 'Não'])].copy()

        if df_votos_validos.empty: return vazio

        # 4. Detectar coluna de ID de votação
        id_votacao_col = next((col for col in df_votos.columns if 'votacao' in col.lower() and 'id' in col.lower()), 'idVotacao')

        # 5. Calcular alinhamento geral por partido
        bancada_voto_majoritario = df_votos_validos.groupby([id_votacao_col, 'sgPartido'])[voto_col].agg(
            lambda x: x.value_counts().index[0]
        ).reset_index()
        bancada_voto_majoritario.rename(columns={voto_col: 'voto_bancada'}, inplace=True)

        df_comparacao = pd.merge(df_votos_validos, bancada_voto_majoritario, on=[id_votacao_col, 'sgPartido'])
        df_comparacao['alinhado'] = (df_comparacao[voto_col] == df_comparacao['voto_bancada']).astype(int)

        alinhamento_final = df_comparacao.groupby('sgPartido')['alinhado'].mean() * 100
        df_alinhamento = alinhamento_final.reset_index(name='perc_alinhamento')

        # 6. Carregar metadados das votações (descrição/tema) do votacoes-*.csv
        arquivos_votacoes_meta = glob.glob(os.path.join('dados', 'votacoes-*.csv'))
        if arquivos_votacoes_meta:
            lista_meta = [pd.read_csv(f, sep=';', encoding='utf-8', on_bad_lines='skip', engine='python') for f in arquivos_votacoes_meta]
            df_meta = pd.concat(lista_meta, ignore_index=True)
            id_meta_col = next((col for col in df_meta.columns if col.lower() == 'id'), 'id')
            desc_col = next((col for col in df_meta.columns if 'descricao' in col.lower() or 'descri' in col.lower()), None)
            prop_col = next((col for col in df_meta.columns if 'proposicao' in col.lower() and 'descri' in col.lower()), None)
            if desc_col:
                df_meta['tema_label'] = df_meta[desc_col].fillna('').astype(str).str.strip()
                if prop_col:
                    mask_vazio = df_meta['tema_label'] == ''
                    df_meta.loc[mask_vazio, 'tema_label'] = df_meta.loc[mask_vazio, prop_col].fillna('Sem descrição').astype(str).str.strip()
            elif prop_col:
                df_meta['tema_label'] = df_meta[prop_col].fillna('Sem descrição').astype(str).str.strip()
            else:
                df_meta['tema_label'] = df_meta[id_meta_col].astype(str)
            df_meta['id_votacao_str'] = df_meta[id_meta_col].astype(str).str.strip()
            df_meta = df_meta[['id_votacao_str', 'tema_label']].drop_duplicates(subset='id_votacao_str')
        else:
            df_meta = pd.DataFrame(columns=['id_votacao_str', 'tema_label'])

        # 7. Calcular % Sim e % Não por partido em cada votação
        df_votos_validos['id_votacao_str'] = df_votos_validos[id_votacao_col].astype(str).str.strip()
        contagem = df_votos_validos.groupby(['id_votacao_str', 'sgPartido', voto_col]).size().reset_index(name='qtd')
        total_por_vot_partido = contagem.groupby(['id_votacao_str', 'sgPartido'])['qtd'].sum().reset_index(name='total')
        contagem = pd.merge(contagem, total_por_vot_partido, on=['id_votacao_str', 'sgPartido'])
        contagem['perc'] = contagem['qtd'] / contagem['total'] * 100
        contagem.rename(columns={voto_col: 'voto'}, inplace=True)
        contagem = pd.merge(contagem, df_meta, on='id_votacao_str', how='left')
        contagem['tema_label'] = contagem['tema_label'].fillna(contagem['id_votacao_str'])

        # 8. Calcular votações mais divididas (menor coesão média entre os partidos)
        coesao = df_votos_validos.groupby(['id_votacao_str', 'sgPartido'])[voto_col].apply(
            lambda x: x.value_counts(normalize=True).iloc[0] * 100
        ).reset_index(name='coesao')
        divisao_por_votacao = coesao.groupby('id_votacao_str')['coesao'].mean().reset_index(name='coesao_media')
        divisao_por_votacao = pd.merge(divisao_por_votacao, df_meta, on='id_votacao_str', how='left')
        divisao_por_votacao['tema_label'] = divisao_por_votacao['tema_label'].fillna(divisao_por_votacao['id_votacao_str'])
        divisao_por_votacao.sort_values('coesao_media', inplace=True)

        return df_alinhamento, contagem, divisao_por_votacao, id_votacao_col, voto_col

    except Exception as e:
        print(f"Erro no cálculo de alinhamento (P10): {e}")
        return (
            pd.DataFrame(columns=['sgPartido', 'perc_alinhamento']),
            pd.DataFrame(),
            pd.DataFrame(),
            '',
            ''
        )

# --- 2. EXECUÇÃO DO CARREGAMENTO ---
# O Streamlit mostra um spinner enquanto carrega
with st.spinner('Carregando dados da 57ª Legislatura (2023-2026)... Pode demorar na primeira vez.'):
    df_principal, df_freq, df_autores, df_temas, df_temas_classificado, df_votos_temas, TEMAS_KEYWORDS = carregar_tudo()
    df_alinhamento, df_votos_contagem, df_divisao, _id_vot_col, _voto_col = carregar_votos_e_calcular_alinhamento(df_principal)

# --- 3. FILTROS LATERAIS (GLOBAIS) ---
st.sidebar.header("🔍 Filtros Globais")
nome_busca = st.sidebar.text_input("Buscar por Nome do Deputado")
partidos_disp = sorted(df_principal['sgPartido'].dropna().unique())
partido_sel = st.sidebar.multiselect("Partidos", partidos_disp)
ufs_disp = sorted(df_principal['sgUF'].dropna().unique())
uf_sel = st.sidebar.multiselect("Estados (UF)", ufs_disp)

# Aplicação dos filtros no dataframe principal
df_filtrado = df_principal.copy()
if nome_busca:
    df_filtrado = df_filtrado[df_filtrado['txNomeParlamentar'].str.contains(nome_busca, case=False, na=False)]
if partido_sel:
    df_filtrado = df_filtrado[df_filtrado['sgPartido'].isin(partido_sel)]
if uf_sel:
    df_filtrado = df_filtrado[df_filtrado['sgUF'].isin(uf_sel)]

# Obter IDs e partidos dos deputados que restaram após o filtro (para P11 e P10)
df_link_partido_filtrado = df_filtrado[['id_oficial', 'sgPartido']].drop_duplicates()

# --- 4. MÉTRICAS GLOBAIS ---
st.title("🏛️ Dashboard Legislativo - 57ª Legislatura (2023-2026)")
m1, m2, m3 = st.columns(3)
m1.metric("Gasto Total Acumulado (Cota)", f"R$ {df_filtrado['vlrLiquido'].sum():,.2f}")
m2.metric("Deputados Analisados (no filtro)", df_filtrado['txNomeParlamentar'].nunique())
m3.metric("Notas Fiscais Processadas", f"{len(df_filtrado):,}")
st.divider()

# --- 5. P1 (RANKING DE GASTOS POR DEPUTADO) ---
st.header("💰 P1 — Ranking de Gastos por Deputado")
col_slider, _ = st.columns([0.4, 0.6])
with col_slider:
    n_top = st.slider("Mostrar quantos deputados no ranking de gastos?", 5, 50, 15)

ranking_gastos = df_filtrado.groupby(['txNomeParlamentar', 'sgPartido', 'sgUF'])['vlrLiquido'].sum().sort_values(ascending=False).reset_index()

fig_p1 = px.bar(
    ranking_gastos.head(n_top), x='vlrLiquido', y='txNomeParlamentar',
    orientation='h', color='vlrLiquido', color_continuous_scale='Reds',
    labels={'vlrLiquido': 'Total Gasto (R$)', 'txNomeParlamentar': 'Deputado'},
    template=template_grafico, hover_data=['sgPartido', 'sgUF']
)
fig_p1.update_layout(yaxis={'categoryorder':'total ascending'}, height=400 + (n_top * 10))
st.plotly_chart(fig_p1, use_container_width=True)
st.divider()

# --- 5b. P2 (AGRUPAMENTO POR EIXO TEMÁTICO) ---
st.header("🗂️ P2 — Agrupamento por Eixo Temático de Atuação")

if df_temas_classificado.empty:
    st.warning("⚠️ Nenhuma proposição classificada encontrada. Verifique se os arquivos `proposicoes-*.csv` e `proposicoesAutores-*.csv` estão na pasta `dados/`.")
else:
    ids_filtrados = df_filtrado['id_oficial'].unique()
    df_tc_filtrado = df_temas_classificado[df_temas_classificado['id_oficial'].isin(ids_filtrados)]

    if df_tc_filtrado.empty:
        st.info("Nenhuma proposição classificada encontrada para os deputados no filtro atual.")
    else:
        perfil_dep = df_tc_filtrado.groupby(['id_oficial', 'tema']).size().reset_index(name='qtd')
        idx_max = perfil_dep.groupby('id_oficial')['qtd'].idxmax()
        tema_dominante = perfil_dep.loc[idx_max][['id_oficial', 'tema']].rename(columns={'tema': 'tema_dominante'})

        contagem_temas = tema_dominante['tema_dominante'].value_counts().reset_index()
        contagem_temas.columns = ['Tema', 'Deputados']

        prop_por_tema = df_tc_filtrado['tema'].value_counts().reset_index()
        prop_por_tema.columns = ['Tema', 'Proposições']

        CORES_TEMAS = {
            'Saúde': '#e74c3c', 'Educação': '#3498db', 'Segurança': '#2c3e50',
            'Tributário': '#f39c12', 'Econômico': '#27ae60', 'Ambiental': '#1abc9c',
            'Infraestrutura': '#8e44ad', 'Social': '#e91e63', 'Agropecuário': '#795548',
        }

        tab_p2a, tab_p2b, tab_p2c, tab_p2d = st.tabs([
            "📊 Proposições por Tema", "👥 Deputados por Tema", "🔍 Perfil Individual", "☁️ Nuvem por Tema"
        ])

        with tab_p2a:
            fig_p2a = px.bar(
                prop_por_tema.sort_values('Proposições'), x='Proposições', y='Tema', orientation='h',
                color='Tema', color_discrete_map=CORES_TEMAS,
                text_auto=True, template=template_grafico,
                title="Total de proposições classificadas por eixo temático"
            )
            fig_p2a.update_layout(yaxis={'categoryorder': 'total ascending'}, showlegend=False, height=450, bargap=0.3)
            fig_p2a.update_traces(textposition='outside', cliponaxis=False)
            st.plotly_chart(fig_p2a, use_container_width=True)

        with tab_p2b:
            fig_p2b = px.bar(
                contagem_temas.sort_values('Deputados'), x='Deputados', y='Tema', orientation='h',
                color='Tema', color_discrete_map=CORES_TEMAS,
                text_auto=True, template=template_grafico,
                title="Número de deputados cujo tema principal de atuação é cada eixo"
            )
            fig_p2b.update_layout(yaxis={'categoryorder': 'total ascending'}, showlegend=False, height=450)
            fig_p2b.update_traces(textposition='outside', cliponaxis=False)
            st.plotly_chart(fig_p2b, use_container_width=True)

            st.subheader("Lista de Deputados por Tema Dominante")
            tema_filtro = st.selectbox("Selecione o tema:", sorted(contagem_temas['Tema'].tolist()), key='tema_lista_p2b')
            deps_tema = tema_dominante[tema_dominante['tema_dominante'] == tema_filtro]['id_oficial'].tolist()
            nomes_tema = df_filtrado[df_filtrado['id_oficial'].isin(deps_tema)][['txNomeParlamentar', 'sgPartido', 'sgUF']].drop_duplicates().sort_values('txNomeParlamentar').reset_index(drop=True)
            nomes_tema.columns = ['Nome', 'Partido', 'UF']
            st.caption(f"{len(nomes_tema)} deputado(s) com tema dominante: **{tema_filtro}**")
            st.dataframe(nomes_tema, use_container_width=True, hide_index=True)

        with tab_p2c:
            lista_deps_p2 = sorted(df_filtrado['txNomeParlamentar'].dropna().unique())
            dep_p2 = st.selectbox("Selecione o deputado:", lista_deps_p2, key='dep_p2')
            id_dep_p2 = None
            dep_p2_rows = df_filtrado[df_filtrado['txNomeParlamentar'] == dep_p2]
            if not dep_p2_rows.empty:
                id_dep_p2 = dep_p2_rows['id_oficial'].iloc[0]
            if id_dep_p2:
                perfil_ind = df_tc_filtrado[df_tc_filtrado['id_oficial'] == id_dep_p2]['tema'].value_counts().reset_index()
                perfil_ind.columns = ['Tema', 'Proposições']
                if perfil_ind.empty:
                    st.info(f"{dep_p2} não possui proposições classificadas nos eixos temáticos.")
                else:
                    fig_ind_p2 = px.pie(
                        perfil_ind, values='Proposições', names='Tema',
                        color='Tema', color_discrete_map=CORES_TEMAS,
                        hole=0.4, template=template_grafico,
                        title=f"Distribuição temática — {dep_p2}"
                    )
                    st.plotly_chart(fig_ind_p2, use_container_width=True)

        with tab_p2d:
            ruido_nuvem = {
                'da', 'do', 'de', 'que', 'em', 'para', 'um', 'uma', 'os', 'as', 'ao', 'aos', 'com', 'por',
                'pela', 'pelo', 'dos', 'das', 'pelos', 'pelas', 'nos', 'nas', 'sob', 'sobre', 'como',
                'na', 'no', 'ou', 'se', 'o', 'a', 'e', 'através', 'seu', 'sua', 'deste', 'desta',
                'à', 'às', 'lei', 'altera', 'dispõe', 'institui', 'cria', 'art', 'projeto', 'requerimento',
                'parecer', 'pauta', 'comissão', 'retirada', 'matéria', 'público', 'pública', 'pl', 'sr',
                'voto', 'votos', 'determina', 'manifesta', 'proíbe', 'torna', 'obriga', 'concede', 'autoriza',
                'brasil', 'república', 'nacional', 'federal', 'estadual', 'municipal', 'deputado', 'câmara',
                'pec', 'plp', 'mpv', 'nº', 'n', 'dá', 'sem', 'dia', 'dias', 'ano', 'anos',
            }
            tema_nuvem = st.selectbox("Selecione o eixo temático:", sorted(TEMAS_KEYWORDS.keys()), key='tema_nuvem_p2d')
            ementas_tema = df_tc_filtrado[df_tc_filtrado['tema'] == tema_nuvem]['ementa'].dropna()
            if len(ementas_tema) == 0:
                st.warning("Nenhuma ementa encontrada para este tema com os filtros atuais.")
            else:
                texto_tema = " ".join(ementas_tema.astype(str)).lower()
                try:
                    wc_tema = WordCloud(
                        width=1400, height=600, background_color='white',
                        stopwords=ruido_nuvem, colormap='tab10', min_font_size=10,
                        max_words=80, collocations=False,
                        regexp=r"\b[a-zA-ZáéíóúçãõâêôàÀíÍóÓúÚáÁéÉãÃõÕçÇ]+\b"
                    ).generate(texto_tema)
                    fig_nuvem_tema, ax_nt = plt.subplots(figsize=(14, 6))
                    ax_nt.imshow(wc_tema, interpolation='bilinear')
                    ax_nt.axis('off')
                    plt.tight_layout(pad=0)
                    st.pyplot(fig_nuvem_tema)
                    plt.close(fig_nuvem_tema)
                    st.caption(f"Nuvem gerada a partir de {len(ementas_tema)} proposições classificadas como **{tema_nuvem}**")
                except ValueError:
                    st.info("Texto insuficiente após filtragem para gerar a nuvem.")

st.divider()

# --- 6. P4 (PERFIL POR ESCOLARIDADE + DETALHAMENTO) ---
st.header("🎓 P4 — Perfil por Escolaridade")

# Pegar apenas 1 linha por deputado (perfil único)
df_u = df_filtrado.drop_duplicates(subset=['id_oficial'])
esc_data = df_u['escolaridade'].value_counts().reset_index()
esc_data.columns = ['Escolaridade', 'Qtd']

# Gráfico Principal P4
fig_p4 = px.bar(
    esc_data, x='Qtd', y='Escolaridade', 
    orientation='h', color='Qtd', color_continuous_scale='Blues', 
    text_auto=True, template=template_grafico,
    labels={'Qtd': 'Número de Deputados'}
)
fig_p4.update_layout(yaxis={'categoryorder':'total ascending'})
st.plotly_chart(fig_p4, use_container_width=True)

# --- DETALHAMENTO DA P4 (Tabela Dinâmica de Deputados) ---
st.subheader("🔍 Ver Deputados por Nível de Escolaridade")
escolaridades_disponiveis = sorted(df_u['escolaridade'].dropna().unique())

if escolaridades_disponiveis:
    # Seletor dinâmico
    nivel_sel = st.selectbox("Selecione um nível de instrução para listar os parlamentares:", escolaridades_disponiveis)
    
    # Filtra os deputados únicos com aquela escolaridade
    df_nivel_sel = df_u[df_u['escolaridade'] == nivel_sel][['txNomeParlamentar', 'sgPartido', 'sgUF']].sort_values(by='txNomeParlamentar')
    
    # Mostra a tabela
    st.markdown(f"**Parlamentares com '{nivel_sel}' ({len(df_nivel_sel)} encontrados):**")
    st.dataframe(df_nivel_sel, use_container_width=True, hide_index=True)
else:
    st.info("Nenhum dado de escolaridade disponível para os filtros atuais.")

st.divider()

# --- 7. P10 (🤝 ALINHAMENTO INTERNO DOS PARTIDOS) ---
st.header("🤝 P10 — Alinhamento Interno dos Partidos (Fidelidade à Bancada)")

partidos_no_filtro = df_filtrado['sgPartido'].unique()
df_alinhamento_filtrado = df_alinhamento[df_alinhamento['sgPartido'].isin(partidos_no_filtro)].copy()

if df_alinhamento_filtrado.empty:
    st.warning("⚠️ Dados de votações (`votacoesVotos-*.csv`) não encontrados na pasta `dados`, insuficientes para os partidos selecionados ou não contêm votos 'Sim'/'Não'. Impossível calcular o alinhamento interno (P10) no momento.")
else:
    tab_p10_geral, tab_p10_busca, tab_p10_divididas = st.tabs([
        "📊 Alinhamento Geral",
        "🔍 Buscar Votação",
        "⚡ Mais Divididas"
    ])

    # ── Aba 1: Alinhamento Geral (original) ──────────────────────────────────
    with tab_p10_geral:
        st.markdown("Porcentagem média de vezes que os deputados de cada partido votaram junto com a maioria da sua própria bancada (em votações Sim/Não).")
        df_alinhamento_filtrado.sort_values(by='perc_alinhamento', ascending=False, inplace=True)
        fig_p10 = px.bar(
            df_alinhamento_filtrado,
            x='sgPartido', y='perc_alinhamento',
            color='perc_alinhamento', color_continuous_scale='Cividis',
            labels={'perc_alinhamento': 'Alinhamento Médio (%)', 'sgPartido': 'Partido'},
            template=template_grafico,
            text_auto='.1f'
        )
        fig_p10.update_layout(xaxis={'categoryorder': 'total descending'})
        st.plotly_chart(fig_p10, use_container_width=True)

    # ── Aba 2: Busca por Votação ──────────────────────────────────────────────
    with tab_p10_busca:
        st.markdown("Busque pelo tema ou descrição de uma votação e veja como cada partido votou.")

        if df_votos_contagem.empty:
            st.info("Dados de votações não disponíveis para a busca.")
        else:
            # Campo de busca
            busca_tema = st.text_input("🔎 Buscar votação por tema/descrição:", placeholder="Ex: reforma, imposto, educação...")

            # Filtrar votações disponíveis para os partidos no filtro global
            df_contagem_filtrada = df_votos_contagem[df_votos_contagem['sgPartido'].isin(partidos_no_filtro)].copy()

            # Obter lista única de votações com seus temas
            opcoes_votacao = df_contagem_filtrada[['id_votacao_str', 'tema_label']].drop_duplicates(subset='id_votacao_str')

            if busca_tema:
                mask_busca = opcoes_votacao['tema_label'].str.contains(busca_tema, case=False, na=False)
                opcoes_votacao = opcoes_votacao[mask_busca]

            if opcoes_votacao.empty:
                st.warning("Nenhuma votação encontrada para esse termo.")
            else:
                # Trunca o label para caber no selectbox
                opcoes_votacao = opcoes_votacao.copy()
                opcoes_votacao['label_curto'] = opcoes_votacao['tema_label'].str[:120]
                mapa_label_id = dict(zip(opcoes_votacao['label_curto'], opcoes_votacao['id_votacao_str']))

                votacao_escolhida_label = st.selectbox(
                    f"{len(opcoes_votacao)} votação(ões) encontrada(s) — selecione uma:",
                    options=list(mapa_label_id.keys())
                )
                votacao_escolhida_id = mapa_label_id[votacao_escolhida_label]

                # Filtra dados da votação selecionada
                df_vot_sel = df_contagem_filtrada[df_contagem_filtrada['id_votacao_str'] == votacao_escolhida_id].copy()

                if not df_vot_sel.empty:
                    fig_busca = px.bar(
                        df_vot_sel,
                        x='sgPartido', y='perc', color='voto',
                        color_discrete_map={'Sim': '#2ecc71', 'Não': '#e74c3c'},
                        barmode='stack',
                        labels={'perc': '% de Votos', 'sgPartido': 'Partido', 'voto': 'Voto'},
                        template=template_grafico,
                        text_auto='.0f'
                    )
                    fig_busca.update_layout(
                        yaxis_title='% de Votos',
                        legend_title='Voto',
                        xaxis={'categoryorder': 'total descending'}
                    )
                    st.plotly_chart(fig_busca, use_container_width=True)

                    # Tabela resumo: voto majoritário por partido
                    resumo = df_vot_sel.loc[df_vot_sel.groupby('sgPartido')['perc'].idxmax()][['sgPartido', 'voto', 'perc']].copy()
                    resumo.columns = ['Partido', 'Voto Majoritário', '% Maioria']
                    resumo['% Maioria'] = resumo['% Maioria'].round(1)
                    resumo.sort_values('Partido', inplace=True)
                    st.markdown("**Voto majoritário por partido nessa votação:**")
                    st.dataframe(resumo, use_container_width=True, hide_index=True)

    # ── Aba 3: Votações Mais Divididas ────────────────────────────────────────
    with tab_p10_divididas:
        st.markdown("Votações onde os partidos tiveram **menor coesão interna** — mais deputados do mesmo partido votando de formas diferentes.")

        if df_divisao.empty:
            st.info("Dados de divisão não disponíveis.")
        else:
            col_n, _ = st.columns([0.3, 0.7])
            with col_n:
                n_divididas = st.slider("Quantas votações exibir?", 5, 30, 10)

            # Filtra só votações que têm dados dos partidos no filtro
            ids_com_dados = df_votos_contagem[df_votos_contagem['sgPartido'].isin(partidos_no_filtro)]['id_votacao_str'].unique()
            df_div_filtrada = df_divisao[df_divisao['id_votacao_str'].isin(ids_com_dados)].head(n_divididas).copy()

            if df_div_filtrada.empty:
                st.warning("Nenhuma votação encontrada para os partidos selecionados.")
            else:
                # Label curto para o eixo
                df_div_filtrada['label_curto'] = df_div_filtrada['tema_label'].str[:60] + '...'

                fig_div = px.bar(
                    df_div_filtrada,
                    x='coesao_media', y='label_curto',
                    orientation='h',
                    color='coesao_media', color_continuous_scale='RdYlGn',
                    labels={'coesao_media': 'Coesão Média dos Partidos (%)', 'label_curto': 'Votação'},
                    template=template_grafico,
                    text_auto='.1f'
                )
                fig_div.update_layout(
                    yaxis={'categoryorder': 'total ascending'},
                    height=150 + (n_divididas * 35),
                    coloraxis_colorbar_title='Coesão (%)'
                )
                st.plotly_chart(fig_div, use_container_width=True)

                # Detalhar uma das votações mais divididas
                st.markdown("---")
                st.markdown("**Ver detalhes de uma dessas votações:**")
                mapa_div = dict(zip(df_div_filtrada['label_curto'], df_div_filtrada['id_votacao_str']))
                vot_div_sel_label = st.selectbox("Selecione a votação:", list(mapa_div.keys()), key='sb_divididas')
                vot_div_sel_id = mapa_div[vot_div_sel_label]

                df_det = df_votos_contagem[
                    (df_votos_contagem['id_votacao_str'] == vot_div_sel_id) &
                    (df_votos_contagem['sgPartido'].isin(partidos_no_filtro))
                ].copy()

                if not df_det.empty:
                    fig_det = px.bar(
                        df_det,
                        x='sgPartido', y='perc', color='voto',
                        color_discrete_map={'Sim': '#2ecc71', 'Não': '#e74c3c'},
                        barmode='stack',
                        labels={'perc': '% de Votos', 'sgPartido': 'Partido', 'voto': 'Voto'},
                        template=template_grafico,
                        text_auto='.0f'
                    )
                    fig_det.update_layout(
                        yaxis_title='% de Votos',
                        legend_title='Voto',
                        xaxis={'categoryorder': 'total descending'}
                    )
                    st.plotly_chart(fig_det, use_container_width=True)

st.divider()

# --- 7b. P3 (🗳️ COMO O DEPUTADO VOTOU POR TEMA) ---
st.header("🗳️ P3 — Como o Deputado Votou por Tema")

if df_votos_temas.empty:
    st.warning("⚠️ Dados insuficientes para P3. Verifique se os arquivos `votacoesVotos-*.csv`, `votacoes-*.csv` e `proposicoes-*.csv` estão na pasta `dados/`.")
else:
    col_p3a, col_p3b = st.columns(2)
    with col_p3a:
        dep_p3 = st.selectbox("Selecione o Deputado:", sorted(df_filtrado['txNomeParlamentar'].dropna().unique()), key='dep_p3')
    with col_p3b:
        tema_p3 = st.selectbox("Selecione o Eixo Temático:", sorted(TEMAS_KEYWORDS.keys()), key='tema_p3')

    id_dep_p3 = None
    dep_rows = df_filtrado[df_filtrado['txNomeParlamentar'] == dep_p3]
    if not dep_rows.empty:
        id_dep_p3 = dep_rows['id_oficial'].iloc[0]

    if id_dep_p3:
        votos_filtro = df_votos_temas[
            (df_votos_temas['id_oficial'] == id_dep_p3) &
            (df_votos_temas['tema'] == tema_p3)
        ]

        if votos_filtro.empty:
            st.info(f"Sem registros de votos de **{dep_p3}** em votações do eixo **{tema_p3}** no período disponível.")
        else:
            votos_agg = votos_filtro['voto'].value_counts().reset_index()
            votos_agg.columns = ['Voto', 'Quantidade']

            fig_p3 = px.pie(
                votos_agg, values='Quantidade', names='Voto',
                color='Voto',
                color_discrete_map={'Sim': '#2ecc71', 'Não': '#e74c3c', 'Obstrução': '#f1c40f', 'Abstenção': '#95a5a6'},
                hole=0.4, template=template_grafico,
                title=f"Votos de {dep_p3} no eixo {tema_p3}"
            )

            col_grafico, col_tabela = st.columns([0.4, 0.6])
            with col_grafico:
                st.plotly_chart(fig_p3, use_container_width=True)
            with col_tabela:
                st.markdown("**Proposições votadas:**")
                tabela_votos = votos_filtro[['voto', 'ementa']].drop_duplicates().reset_index(drop=True)
                tabela_votos.columns = ['Voto', 'Ementa']
                st.dataframe(tabela_votos, use_container_width=True, hide_index=True)

st.divider()

# --- 8. P11 (BARRA DE ABAS - RANKING DE PARTIDOS) ---
st.header("📊 P11 — Ranking de Partidos (Atividade e Gastos)")

# Preparação de dados agrupados por partido respeitando o FILTRO GLOBAL de despesas
df_partidos_P11 = df_filtrado.groupby('sgPartido').agg({'vlrLiquido': 'sum'}).reset_index()

# Adicionar Frequência Média (calculada globalmente e mapeada)
df_partidos_P11['perc_frequencia'] = df_partidos_P11['sgPartido'].map(df_freq).fillna(0)

# Adicionar Produção (contar proposições cruzando autores com partidos FILTRADOS)
df_prod_partido = pd.merge(df_autores, df_link_partido_filtrado, on='id_oficial', how='inner')
contagem_prod_partido = df_prod_partido.groupby('sgPartido').size()
df_partidos_P11['qtd_proposicoes'] = df_partidos_P11['sgPartido'].map(contagem_prod_partido).fillna(0)

# Criação das Abas a, b, c, d
tab_a, tab_b, tab_c, tab_d = st.tabs(["a) Frequência (%)", "b) Proposições", "c) Gastos Totais", "d) Nuvem de Temas"])

with tab_a:
    st.subheader("Média de Presença em Eventos por Partido (%)")
    fig_a = px.bar(df_partidos_P11.sort_values('perc_frequencia', ascending=False), x='sgPartido', y='perc_frequencia', color='perc_frequencia', color_continuous_scale='Viridis', template=template_grafico, labels={'perc_frequencia': 'Frequência Média (%)'})
    st.plotly_chart(fig_a, use_container_width=True)

with tab_b:
    st.subheader("Total de Proposições Legislativas por Partido")
    fig_b = px.bar(df_partidos_P11.sort_values('qtd_proposicoes', ascending=False), x='sgPartido', y='qtd_proposicoes', color='qtd_proposicoes', color_continuous_scale='Greens', template=template_grafico, labels={'qtd_proposicoes': 'Número de Proposições'})
    st.plotly_chart(fig_b, use_container_width=True)

with tab_c:
    st.subheader("Gasto Total Acumulado (Cota Parlamentar) por Partido")
    fig_c = px.bar(df_partidos_P11.sort_values('vlrLiquido', ascending=False), x='sgPartido', y='vlrLiquido', color='vlrLiquido', color_continuous_scale='Reds', template=template_grafico, labels={'vlrLiquido': 'Total Gasto (R$)'})
    st.plotly_chart(fig_c, use_container_width=True)

with tab_d:
    st.subheader("Nuvem de Temas mais Tratados pelo Partido")
    # Usa apenas os partidos que restaram no filtro global para o seletor da nuvem
    partidos_nuvem = sorted(df_partidos_P11['sgPartido'].unique())
    
    if partidos_nuvem:
        partido_n = st.selectbox("Selecione o Partido para gerar a Nuvem de Palavras:", partidos_nuvem, key='sb_nuvem')
        
        # Filtro robusto de ementas (garantindo strings limpas)
        ids_dep_partido = df_link_partido_filtrado[df_link_partido_filtrado['sgPartido'] == partido_n]['id_oficial'].astype(str).str.strip().unique()
        df_temas_clean = df_temas.copy()
        df_temas_clean['id_oficial'] = df_temas_clean['id_oficial'].astype(str).str.strip()
        ementas_partido = df_temas_clean[df_temas_clean['id_oficial'].isin(ids_dep_partido)]['ementa'].dropna()
        texto = " ".join(ementas_partido.astype(str))
        
        if len(texto) > 10:
            try:
                # Stopwords legislativas básicas para limpar a nuvem
                stop_leg = {'lei', 'altera', 'dispõe', 'institui', 'cria', 'nº', 'art', 'projeto', 'requerimento', 'comissão', 'da', 'do', 'que', 'em', 'para', 'com', 'o', 'a', 'os', 'as'}
                wc = WordCloud(width=800, height=400, background_color='white', stopwords=stop_leg, colormap='tab10').generate(texto.lower())
                fig_d, ax = plt.subplots(figsize=(10, 5))
                ax.imshow(wc, interpolation='bilinear')
                ax.axis('off')
                st.pyplot(fig_d)
                plt.close(fig_d)
            except ValueError:
                 st.warning("Não foi possível gerar a nuvem para este partido (texto insuficiente após filtragem).")
        else:
            st.warning("Pouco texto disponível nas ementas para gerar a nuvem deste partido.")
    else:
        st.info("Nenhum partido disponível para gerar nuvem com os filtros atuais.")
st.divider()

# --- 9. P13 (TIPOS DE DESPESA - VISÃO GERAL E INDIVIDUAL) ---
st.header("📑 P13 — Tipos de Despesa (Cota Parlamentar)")
col_vazia_l, col_conteudo_p13, col_vazia_r = st.columns([0.15, 0.7, 0.15])

with col_conteudo_p13:
    tab_global, tab_individual = st.tabs(["🌎 Visão Geral (Todos no Filtro)", "👤 Visão por Deputado"])
    
    with tab_global:
        cat_data = df_filtrado.groupby('txtDescricao')['vlrLiquido'].sum().reset_index()
        if not cat_data.empty:
            fig_global = px.pie(cat_data, values='vlrLiquido', names='txtDescricao', hole=0.4, template=template_grafico, title="Distribuição de Gastos por Categoria")
            fig_global.update_layout(showlegend=True) # Ativei a legenda aqui
            st.plotly_chart(fig_global, use_container_width=True)
        else:
            st.info("Nenhum dado de despesa encontrado para os filtros atuais.")

    with tab_individual:
        # Seletor independente para P13 Individual respeitando o FILTRO GLOBAL
        lista_nomes_P13 = sorted(df_filtrado['txNomeParlamentar'].dropna().unique())
        if len(lista_nomes_P13) > 0:
            dep_escolhido = st.selectbox("Selecione um deputado para análise individual de gastos:", lista_nomes_P13, key='sb_dep_p13')
            df_ind = df_filtrado[df_filtrado['txNomeParlamentar'] == dep_escolhido]
            cat_ind = df_ind.groupby('txtDescricao')['vlrLiquido'].sum().reset_index()
            
            if not cat_ind.empty:
                st.info(f"Total gasto acumulado (2023-2026) por {dep_escolhido}: **R$ {df_ind['vlrLiquido'].sum():,.2f}**")
                fig_ind = px.pie(cat_ind, values='vlrLiquido', names='txtDescricao', hole=0.4, color_discrete_sequence=px.colors.qualitative.Safe, title=f"Distribuição de Gastos de {dep_escolhido}")
                st.plotly_chart(fig_ind, use_container_width=True)
            else:
                 st.warning(f"O deputado {dep_escolhido} está no filtro, mas não possui registros de despesas.")
        else:
            st.warning("Nenhum deputado encontrado com os filtros atuais.")
