import streamlit as st
import pandas as pd
import plotly.express as px
import sqlite3
import re
from wordcloud import WordCloud
import matplotlib.pyplot as plt

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Dashboard Legislativo 2023-2026", page_icon="🏛️", layout="wide")
template_grafico = "plotly_white"

# --- 1. FUNÇÕES DE CARREGAMENTO DE DADOS (COM CACHE) ---

STOPWORDS_LEGISLATIVAS = {
    # Verbos de ação genéricos
    'alteração', 'criação', 'instituição', 'estabelecimento', 'regulamentação',
    'dispõe', 'dispoe', 'denominação', 'concessão', 'autorização', 'proibição',
    'inclusão', 'exclusão', 'revogação', 'acréscimo', 'adequação', 'fixação',
    'determinação', 'definição', 'vedação', 'obrigatoriedade', 'implementação',
    # Termos processuais/legislativos genéricos
    'lei federal', 'lei complementar', 'projeto de lei', 'medida provisória',
    'decreto', 'norma', 'dispositivo', 'artigo', 'parágrafo', 'inciso',
    'regulamento', 'normatização', 'legislação', 'lei',
    'código', 'estatuto', 'diretrizes', 'critério', 'critérios', 'prazo',
    'programa', 'política pública', 'política', 'plano', 'programa (administração)',
    # Termos de resultado genéricos
    'incentivo', 'benefício', 'proteção', 'promoção', 'fomento', 'apoio',
    'redução', 'aumento', 'ampliação', 'suspensão', 'utilização', 'combate',
    'fiscalização', 'controle', 'gestão', 'financiamento',
}

def obter_frequencia_palavras_chave(serie_palavras):
    # 1. Transforma em minúsculo e remove o ponto final
    pc = serie_palavras.astype(str).str.lower().str.replace('.', '', regex=False)

    # 2. Separa por vírgula e explode as listas em várias linhas
    pc = pc.str.split(',').explode()

    # 3. Remove espaços em branco
    pc = pc.str.strip()

    # 4. Desconsidera strings vazias ou "nan"
    pc = pc[(pc != '') & (pc != 'nan')]

    # 5. Remove stopwords legislativas genéricas
    pc = pc[~pc.isin(STOPWORDS_LEGISLATIVAS)]

    # 6. Remove palavras muito curtas (1-2 caracteres)
    pc = pc[pc.str.len() > 2]

    # 7. Conta a frequência
    freq = pc.value_counts()

    return freq

@st.cache_data
def carregar_tudo():
    # Conecta ao banco de dados SQLite
    conn = sqlite3.connect('banco.db')
    cursor = conn.cursor()
    
    # A. GASTOS + PERFIL (P1, P4, P13)
    # Usar o LEFT JOIN e a cláusula AS para que o Pandas receba os nomes de colunas que o Frontend já espera
    query_principal = """
    SELECT 
        d.dep_id AS id_oficial,
        d.dep_nome_eleitoral AS txNomeParlamentar,
        d.dep_escolaridade AS escolaridade,
        desp.desp_sigla_partido AS sgPartido,
        desp.desp_sigla_uf AS sgUF,
        desp.desp_valor_liquido AS vlrLiquido,
        desp.desp_desc_subcota AS txtDescricao
    FROM Despesa desp
    LEFT JOIN Deputado d ON desp.dep_id = d.dep_id
    """
    df_principal = pd.read_sql_query(query_principal, conn)
    df_principal['id_oficial'] = df_principal['id_oficial'].astype(str).str.split('.').str[0]
    
    # B. FREQUÊNCIA (P11a)
    # Conta presenças apenas em Sessões Deliberativas (obrigatórias para todos os deputados)
    query_presenca = """
    SELECT p.dep_id AS id_oficial, COUNT(p.evt_id) as qtd
    FROM PresencaDeputado p
    JOIN Evento e ON p.evt_id = e.evt_id
    WHERE e.evt_tipo = 'Sessão Deliberativa'
    GROUP BY p.dep_id
    """
    df_pres = pd.read_sql_query(query_presenca, conn)
    df_pres['id_oficial'] = df_pres['id_oficial'].astype(str).str.split('.').str[0]
    mapeamento_partido = df_principal[['id_oficial', 'sgPartido']].drop_duplicates()
    df_freq_final = pd.merge(df_pres, mapeamento_partido, on='id_oficial')
    frequencia_partido = df_freq_final.groupby('sgPartido')['qtd'].mean()
    
    # C. PRODUÇÃO (P11b)
    query_autores = """
    SELECT 
        dep_id AS id_oficial, 
        prop_id AS idProposicao_link 
    FROM ProposicaoAutor
    WHERE dep_id IS NOT NULL
    """
    df_autores = pd.read_sql_query(query_autores, conn)
    df_autores['id_oficial'] = df_autores['id_oficial'].astype(str).str.split('.').str[0]
    df_autores['idProposicao_link'] = df_autores['idProposicao_link'].astype(str).str.split('.').str[0]
    
    # D. EMENTAS PARA NUVEM (P11d) e TEMAS
    query_prop = "SELECT prop_id AS idProposicao_link, prop_ementa AS ementa, prop_palavras_chave AS palavras_chave FROM Proposicao"
    df_prop = pd.read_sql_query(query_prop, conn)
    df_prop['idProposicao_link'] = df_prop['idProposicao_link'].astype(str).str.split('.').str[0]

    df_temas = pd.merge(df_autores, df_prop, on='idProposicao_link', how='inner')

    # E. CLASSIFICAÇÃO TEMÁTICA (P3)
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

    # F. VOTOS POR TEMA (P3)
    query_votos_p3 = """
    SELECT 
        vd.dep_id AS id_oficial,
        vd.voto_opcao AS voto,
        v.prop_id AS idProposicao_link,
        v.vot_registro AS hora_votacao,
        v.vot_descricao AS descricao_votacao
    FROM VotoDeputado vd
    JOIN Votacao v ON vd.vot_id = v.vot_id
    WHERE v.prop_id IS NOT NULL
    """
    df_votos_detalhado = pd.read_sql_query(query_votos_p3, conn)
    df_votos_detalhado['id_oficial'] = df_votos_detalhado['id_oficial'].astype(str).str.split('.').str[0]
    df_votos_detalhado['idProposicao_link'] = df_votos_detalhado['idProposicao_link'].astype(str).str.split('.').str[0]
    
    df_votos_temas = pd.merge(df_votos_detalhado, df_temas_classificado[['idProposicao_link', 'tema', 'ementa']], on='idProposicao_link', how='inner')

    conn.close()
    return df_principal, frequencia_partido, df_autores, df_temas, df_temas_classificado, df_votos_temas, TEMAS_KEYWORDS

@st.cache_data
def carregar_votos_e_calcular_alinhamento(df_principal_completo):
    conn = sqlite3.connect('banco.db')
    
    vazio = (pd.DataFrame(columns=['sgPartido', 'perc_alinhamento']), pd.DataFrame(), pd.DataFrame(), '', '')

    # E. VOTOS (P10)
    query_votos = """
    SELECT 
        vot_id AS idVotacao, 
        dep_id AS id_oficial, 
        voto_opcao AS voto 
    FROM VotoDeputado
    """
    df_votos = pd.read_sql_query(query_votos, conn)
    
    if df_votos.empty:
        conn.close()
        return vazio

    df_votos['id_oficial'] = df_votos['id_oficial'].astype(str).str.split('.').str[0]

    # Mapeamento Deputado -> Partido
    mapeamento_partido = df_principal_completo[['id_oficial', 'sgPartido']].drop_duplicates()
    df_votos_partido = pd.merge(df_votos, mapeamento_partido, on='id_oficial', how='inner')

    # Filtrar votos válidos (Sim ou Não)
    df_votos_validos = df_votos_partido[df_votos_partido['voto'].isin(['Sim', 'Não'])].copy()

    if df_votos_validos.empty:
        conn.close()
        return vazio

    id_votacao_col = 'idVotacao'
    voto_col = 'voto'

    # Calcular alinhamento geral por partido
    bancada_voto_majoritario = df_votos_validos.groupby([id_votacao_col, 'sgPartido'])[voto_col].agg(
        lambda x: x.value_counts().index[0]
    ).reset_index()
    bancada_voto_majoritario.rename(columns={voto_col: 'voto_bancada'}, inplace=True)

    df_comparacao = pd.merge(df_votos_validos, bancada_voto_majoritario, on=[id_votacao_col, 'sgPartido'])
    df_comparacao['alinhado'] = (df_comparacao[voto_col] == df_comparacao['voto_bancada']).astype(int)

    alinhamento_final = df_comparacao.groupby('sgPartido')['alinhado'].mean() * 100
    df_alinhamento = alinhamento_final.reset_index(name='perc_alinhamento')

    # Carregar metadados das votações
    query_meta = "SELECT vot_id AS id_votacao_str, vot_descricao AS tema_label FROM Votacao"
    df_meta = pd.read_sql_query(query_meta, conn)
    df_meta['id_votacao_str'] = df_meta['id_votacao_str'].astype(str)
    df_meta['tema_label'] = df_meta['tema_label'].fillna(df_meta['id_votacao_str']).astype(str)

    # Calcular % Sim e % Não por partido
    df_votos_validos['id_votacao_str'] = df_votos_validos[id_votacao_col].astype(str).str.strip()
    contagem = df_votos_validos.groupby(['id_votacao_str', 'sgPartido', voto_col]).size().reset_index(name='qtd')
    total_por_vot_partido = contagem.groupby(['id_votacao_str', 'sgPartido'])['qtd'].sum().reset_index(name='total')
    contagem = pd.merge(contagem, total_por_vot_partido, on=['id_votacao_str', 'sgPartido'])
    contagem['perc'] = contagem['qtd'] / contagem['total'] * 100
    contagem.rename(columns={voto_col: 'voto'}, inplace=True)
    contagem = pd.merge(contagem, df_meta, on='id_votacao_str', how='left')
    contagem['tema_label'] = contagem['tema_label'].fillna(contagem['id_votacao_str'])

    # Calcular votações mais divididas
    coesao = df_votos_validos.groupby(['id_votacao_str', 'sgPartido'])[voto_col].apply(
        lambda x: x.value_counts(normalize=True).iloc[0] * 100
    ).reset_index(name='coesao')
    divisao_por_votacao = coesao.groupby('id_votacao_str')['coesao'].mean().reset_index(name='coesao_media')
    divisao_por_votacao = pd.merge(divisao_por_votacao, df_meta, on='id_votacao_str', how='left')
    divisao_por_votacao['tema_label'] = divisao_por_votacao['tema_label'].fillna(divisao_por_votacao['id_votacao_str'])
    divisao_por_votacao.sort_values('coesao_media', inplace=True)

    conn.close()
    return df_alinhamento, contagem, divisao_por_votacao, id_votacao_col, voto_col


# --- 2. EXECUÇÃO DO CARREGAMENTO ---
with st.spinner('Consultando os dados da 57ª Legislatura...'):
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
st.plotly_chart(fig_p1, width='stretch')
st.divider()

# --- 5b. P2 (AGRUPAMENTO POR EIXO TEMÁTICO) ---
st.header("🗂️ P2 — Agrupamento por Eixo Temático de Atuação")

if df_temas_classificado.empty:
    st.warning("⚠️ Nenhuma proposição classificada encontrada.")
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
            st.plotly_chart(fig_p2a, width='stretch')

        with tab_p2b:
            fig_p2b = px.bar(
                contagem_temas.sort_values('Deputados'), x='Deputados', y='Tema', orientation='h',
                color='Tema', color_discrete_map=CORES_TEMAS,
                text_auto=True, template=template_grafico,
                title="Número de deputados cujo tema principal de atuação é cada eixo"
            )
            fig_p2b.update_layout(yaxis={'categoryorder': 'total ascending'}, showlegend=False, height=450)
            fig_p2b.update_traces(textposition='outside', cliponaxis=False)
            st.plotly_chart(fig_p2b, width='stretch')

            st.subheader("Lista de Deputados por Tema Dominante")
            tema_filtro = st.selectbox("Selecione o tema:", sorted(contagem_temas['Tema'].tolist()), key='tema_lista_p2b')
            deps_tema = tema_dominante[tema_dominante['tema_dominante'] == tema_filtro]['id_oficial'].tolist()
            nomes_tema = df_filtrado[df_filtrado['id_oficial'].isin(deps_tema)][['txNomeParlamentar', 'sgPartido', 'sgUF']].drop_duplicates().sort_values('txNomeParlamentar').reset_index(drop=True)
            nomes_tema.columns = ['Nome', 'Partido', 'UF']
            st.caption(f"{len(nomes_tema)} deputado(s) com tema dominante: **{tema_filtro}**")
            st.dataframe(nomes_tema, width='stretch', hide_index=True)

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
                    st.plotly_chart(fig_ind_p2, width='stretch')

        with tab_p2d:
            tema_nuvem = st.selectbox("Selecione o eixo temático:", sorted(TEMAS_KEYWORDS.keys()), key='tema_nuvem_p2d')
            palavras_tema = df_tc_filtrado[df_tc_filtrado['tema'] == tema_nuvem]['palavras_chave'].dropna()
            
            if len(palavras_tema) == 0:
                st.warning("Nenhuma palavra-chave encontrada para este tema com os filtros atuais.")
            else:
                freq_palavras = obter_frequencia_palavras_chave(palavras_tema)
                
                if freq_palavras.empty:
                    st.info("Texto insuficiente para gerar a nuvem.")
                else:
                    col_nuvem, col_tabela = st.columns([0.7, 0.3])
                    
                    with col_nuvem:
                        wc_tema = WordCloud(
                            width=900, height=500, background_color='white',
                            colormap='tab10', min_font_size=10, max_words=80
                        ).generate_from_frequencies(freq_palavras.to_dict())
                        
                        fig_nuvem_tema, ax_nt = plt.subplots(figsize=(12, 6))
                        ax_nt.imshow(wc_tema, interpolation='bilinear')
                        ax_nt.axis('off')
                        plt.tight_layout(pad=0)
                        st.pyplot(fig_nuvem_tema)
                        plt.close(fig_nuvem_tema)
                        st.caption(f"Nuvem gerada a partir de proposições classificadas como **{tema_nuvem}**")
                    
                    with col_tabela:
                        df_freq_tema = pd.DataFrame({'Palavra-chave': freq_palavras.index, 'Frequência': freq_palavras.values})
                        st.dataframe(df_freq_tema, hide_index=True, height=450, use_container_width=True)

st.divider()

# --- 5c. P3 (🗳️ COMO O DEPUTADO VOTOU POR TEMA) ---
st.header("🗳️ P3 — Como o Deputado Votou por Tema")

if df_votos_temas.empty:
    st.warning("⚠️ Dados insuficientes para P3.")
else:
    # @st.fragment transforma essa função numa "bolha" independente.
    # Cliques aqui dentro não recarregam o resto da página.
    @st.fragment
    def renderizar_p3_interativa():
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
            ].copy()

            if votos_filtro.empty:
                st.info(f"Sem registros de votos de **{dep_p3}** em votações do eixo **{tema_p3}** no período disponível.")
            else:
                if 'hora_votacao' in votos_filtro.columns:
                    votos_filtro['hora_votacao'] = pd.to_datetime(votos_filtro['hora_votacao'], errors='coerce')
                    votos_filtro = votos_filtro.sort_values('hora_votacao', ascending=False)

                tipos_disponiveis = votos_filtro['voto'].unique().tolist()
                
                st.markdown("Filtrar visualização (clique para ocultar/mostrar):")
                cols = st.columns(len(tipos_disponiveis) + 1) 
                
                tipos_selecionados = []
                for i, tipo in enumerate(tipos_disponiveis):
                    if tipo == 'Sim': label = "🟢 Sim"
                    elif tipo == 'Não': label = "🔴 Não"
                    else: label = f"⚪ {tipo}"
                    
                    # Adicionar o nome do deputado na "key" para o Streamlit não se confundir ao trocar de parlamentar
                    if cols[i].checkbox(label, value=True, key=f"chk_{tipo}_{dep_p3}_{tema_p3}"):
                        tipos_selecionados.append(tipo)

                votos_exibicao = votos_filtro[votos_filtro['voto'].isin(tipos_selecionados)]

                def formatar_data_hora(valor_dt):
                    if pd.notnull(valor_dt):
                        return f"🕒 {valor_dt.strftime('%d/%m/%Y às %H:%M')} | "
                    return ""

                st.caption(f"Exibindo {len(votos_exibicao)} votação(ões) correspondente(s) aos filtros.")

                if votos_exibicao.empty:
                    st.warning("Nenhum voto corresponde aos tipos selecionados no filtro.")
                else:
                    with st.container(height=600):
                        for idx, row in votos_exibicao.iterrows():
                            voto_atual = row['voto']
                            data_formatada = formatar_data_hora(row.get('hora_votacao'))

                            # --- Formatar resultado da votação ---
                            descricao_raw = str(row.get('descricao_votacao', '') or '')
                            # Extrair placar (ex: "Sim: 274; Não: 101; Total: 375")
                            placar_match = re.search(r'(Sim:\s*\d+[\s;,]*Não:\s*\d+[\s;,]*Total:\s*\d+)', descricao_raw, re.IGNORECASE)
                            placar = placar_match.group(1) if placar_match else None
                            # Limpar a descrição: remover placar embutido, truncar se longa
                            desc_limpa = re.sub(r'\s*[\.\s]*(Sim:\s*\d+[\s;,]*Não:\s*\d+[\s;,]*Total:\s*\d+)', '', descricao_raw).strip()
                            if len(desc_limpa) > 180:
                                desc_limpa = desc_limpa[:180].rsplit(' ', 1)[0] + '…'

                            # --- Formatar ementa do projeto ---
                            ementa_raw = str(row.get('ementa', '') or '')
                            # Extrair número do projeto (ex: PL 1234/2023, PEC 45/2024)
                            proj_match = re.search(r'\b(PL|PEC|PLN|MPV|PDC|PLP|PRC|REQ|MSC|PDL)\s*[nº°.]?\s*(\d+[\./]\d+)', ementa_raw, re.IGNORECASE)
                            num_projeto = proj_match.group(0).upper() if proj_match else None
                            # Extrair trecho mais informativo: pegar o conteúdo entre aspas se houver
                            trecho_aspas = re.search(r'["\u201c\u201d](.{20,300}?)["\u201c\u201d]', ementa_raw)
                            if trecho_aspas:
                                ementa_resumida = trecho_aspas.group(1).strip()
                            else:
                                # Remover prefixos burocráticos comuns
                                ementa_limpa = re.sub(
                                    r'^(Apresentação d[oa]|Parecer proferido em Plenário pel[oa] Relator[a]?,?\s*[^,]+,\s*(pela|pelo)\s*[^,]+,\s*que conclui pela\s*)',
                                    '', ementa_raw, flags=re.IGNORECASE
                                ).strip()
                                ementa_resumida = ementa_limpa[:220].rsplit(' ', 1)[0] + '…' if len(ementa_limpa) > 220 else ementa_limpa

                            # --- Montar card ---
                            if voto_atual == 'Sim':
                                icone, cor_borda = "🟢", "#2ecc71"
                                fn_card = st.success
                            elif voto_atual == 'Não':
                                icone, cor_borda = "🔴", "#e74c3c"
                                fn_card = st.error
                            else:
                                icone, cor_borda = "⚪", "#f39c12"
                                fn_card = st.warning

                            linhas = [f"{icone} {data_formatada}**Votou: {voto_atual}**"]
                            if num_projeto:
                                linhas.append(f"🗂️ **Projeto:** `{num_projeto}`")
                            if placar:
                                linhas.append(f"📊 **Resultado:** {placar}")
                            linhas.append(f"**Objeto:** {desc_limpa}")

                            fn_card("\n\n".join(linhas))

                            if ementa_resumida:
                                with st.expander("📄 Ver ementa do projeto"):
                                    st.write(ementa_resumida)
                            st.markdown("")

    renderizar_p3_interativa()

st.divider()

# --- 6. P4 (PERFIL POR ESCOLARIDADE + DETALHAMENTO) ---
st.header("🎓 P4 — Perfil por Escolaridade")

df_u = df_filtrado.drop_duplicates(subset=['id_oficial'])
esc_data = df_u['escolaridade'].value_counts().reset_index()
esc_data.columns = ['Escolaridade', 'Qtd']

fig_p4 = px.bar(
    esc_data, x='Qtd', y='Escolaridade', 
    orientation='h', color='Qtd', color_continuous_scale='Blues', 
    text_auto=True, template=template_grafico,
    labels={'Qtd': 'Número de Deputados'}
)
fig_p4.update_layout(yaxis={'categoryorder':'total ascending'})
st.plotly_chart(fig_p4, width='stretch')

st.subheader("🔍 Ver Deputados por Nível de Escolaridade")
escolaridades_disponiveis = sorted(df_u['escolaridade'].dropna().unique())

if escolaridades_disponiveis:
    nivel_sel = st.selectbox("Selecione um nível de instrução para listar os parlamentares:", escolaridades_disponiveis)
    df_nivel_sel = df_u[df_u['escolaridade'] == nivel_sel][['txNomeParlamentar', 'sgPartido', 'sgUF']].sort_values(by='txNomeParlamentar')
    st.markdown(f"**Parlamentares com '{nivel_sel}' ({len(df_nivel_sel)} encontrados):**")
    st.dataframe(df_nivel_sel, width='stretch', hide_index=True)
else:
    st.info("Nenhum dado de escolaridade disponível para os filtros atuais.")

st.divider()

# --- 7. P10 (🤝 ALINHAMENTO INTERNO DOS PARTIDOS) ---
st.header("🤝 P10 — Alinhamento Interno dos Partidos (Fidelidade à Bancada)")

partidos_no_filtro = df_filtrado['sgPartido'].unique()
df_alinhamento_filtrado = df_alinhamento[df_alinhamento['sgPartido'].isin(partidos_no_filtro)].copy()

if df_alinhamento_filtrado.empty:
    st.warning("⚠️ Dados de votações insuficientes para os partidos selecionados ou não contêm votos 'Sim'/'Não'. Impossível calcular o alinhamento interno (P10) no momento.")
else:
    tab_p10_geral, tab_p10_busca, tab_p10_divididas = st.tabs([
        "📊 Alinhamento Geral",
        "🔍 Buscar Votação",
        "⚡ Mais Divididas"
    ])

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
        st.plotly_chart(fig_p10, width='stretch')

    with tab_p10_busca:
        st.markdown("Busque pelo tema ou descrição de uma votação e veja como cada partido votou.")

        if df_votos_contagem.empty:
            st.info("Dados de votações não disponíveis para a busca.")
        else:
            busca_tema = st.text_input("🔎 Buscar votação por tema/descrição:", placeholder="Ex: reforma, imposto, educação...")
            df_contagem_filtrada = df_votos_contagem[df_votos_contagem['sgPartido'].isin(partidos_no_filtro)].copy()
            opcoes_votacao = df_contagem_filtrada[['id_votacao_str', 'tema_label']].drop_duplicates(subset='id_votacao_str')

            if busca_tema:
                mask_busca = opcoes_votacao['tema_label'].str.contains(busca_tema, case=False, na=False)
                opcoes_votacao = opcoes_votacao[mask_busca]

            if opcoes_votacao.empty:
                st.warning("Nenhuma votação encontrada para esse termo.")
            else:
                opcoes_votacao = opcoes_votacao.copy()
                opcoes_votacao['label_curto'] = opcoes_votacao['tema_label'].str[:120]
                mapa_label_id = dict(zip(opcoes_votacao['label_curto'], opcoes_votacao['id_votacao_str']))

                votacao_escolhida_label = st.selectbox(
                    f"{len(opcoes_votacao)} votação(ões) encontrada(s) — selecione uma:",
                    options=list(mapa_label_id.keys())
                )
                votacao_escolhida_id = mapa_label_id[votacao_escolhida_label]
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
                    fig_busca.update_layout(yaxis_title='% de Votos', legend_title='Voto', xaxis={'categoryorder': 'total descending'})
                    st.plotly_chart(fig_busca, width='stretch')

                    resumo = df_vot_sel.loc[df_vot_sel.groupby('sgPartido')['perc'].idxmax()][['sgPartido', 'voto', 'perc']].copy()
                    resumo.columns = ['Partido', 'Voto Majoritário', '% Maioria']
                    resumo['% Maioria'] = resumo['% Maioria'].round(1)
                    resumo.sort_values('Partido', inplace=True)
                    st.markdown("**Voto majoritário por partido nessa votação:**")
                    st.dataframe(resumo, width='stretch', hide_index=True)

    with tab_p10_divididas:
        st.markdown("Votações onde os partidos tiveram **menor coesão interna** — mais deputados do mesmo partido votando de formas diferentes.")

        if df_divisao.empty:
            st.info("Dados de divisão não disponíveis.")
        else:
            col_n, _ = st.columns([0.3, 0.7])
            with col_n:
                n_divididas = st.slider("Quantas votações exibir?", 5, 30, 10)

            ids_com_dados = df_votos_contagem[df_votos_contagem['sgPartido'].isin(partidos_no_filtro)]['id_votacao_str'].unique()
            df_div_filtrada = df_divisao[df_divisao['id_votacao_str'].isin(ids_com_dados)].head(n_divididas).copy()

            if df_div_filtrada.empty:
                st.warning("Nenhuma votação encontrada para os partidos selecionados.")
            else:
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
                fig_div.update_layout(yaxis={'categoryorder': 'total ascending'}, height=150 + (n_divididas * 35), coloraxis_colorbar_title='Coesão (%)')
                st.plotly_chart(fig_div, width='stretch')

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
                    fig_det.update_layout(yaxis_title='% de Votos', legend_title='Voto', xaxis={'categoryorder': 'total descending'})
                    st.plotly_chart(fig_det, width='stretch')

st.divider()

# --- 8. P11 (BARRA DE ABAS - RANKING DE PARTIDOS) ---
st.header("📊 P11 — Ranking de Partidos (Atividade e Gastos)")

df_partidos_P11 = df_filtrado.groupby('sgPartido').agg({'vlrLiquido': 'sum'}).reset_index()
df_partidos_P11['perc_frequencia'] = df_partidos_P11['sgPartido'].map(df_freq).fillna(0)

df_prod_partido = pd.merge(df_autores, df_link_partido_filtrado, on='id_oficial', how='inner')
contagem_prod_partido = df_prod_partido.groupby('sgPartido').size()
df_partidos_P11['qtd_proposicoes'] = df_partidos_P11['sgPartido'].map(contagem_prod_partido).fillna(0)

tab_a, tab_b, tab_c, tab_d = st.tabs(["a) Frequência (Sessões)", "b) Proposições", "c) Gastos Totais", "d) Nuvem de Temas"])

with tab_a:
    st.subheader("Média de Sessões Deliberativas Comparecidas por Deputado (por Partido)")
    fig_a = px.bar(df_partidos_P11.sort_values('perc_frequencia', ascending=False), x='sgPartido', y='perc_frequencia', color='perc_frequencia', color_continuous_scale='Viridis', template=template_grafico, labels={'perc_frequencia': 'Média de Sessões Comparecidas'})
    st.plotly_chart(fig_a, width='stretch')

with tab_b:
    st.subheader("Total de Proposições Legislativas por Partido")
    fig_b = px.bar(df_partidos_P11.sort_values('qtd_proposicoes', ascending=False), x='sgPartido', y='qtd_proposicoes', color='qtd_proposicoes', color_continuous_scale='Greens', template=template_grafico, labels={'qtd_proposicoes': 'Número de Proposições'})
    st.plotly_chart(fig_b, width='stretch')

with tab_c:
    st.subheader("Gasto Total Acumulado (Cota Parlamentar) por Partido")
    fig_c = px.bar(df_partidos_P11.sort_values('vlrLiquido', ascending=False), x='sgPartido', y='vlrLiquido', color='vlrLiquido', color_continuous_scale='Reds', template=template_grafico, labels={'vlrLiquido': 'Total Gasto (R$)'})
    st.plotly_chart(fig_c, width='stretch')

with tab_d:
    st.subheader("Nuvem de Temas mais Tratados pelo Partido")
    partidos_nuvem = sorted(df_partidos_P11['sgPartido'].unique())
    
    if partidos_nuvem:
        partido_n = st.selectbox("Selecione o Partido para gerar a Nuvem de Palavras:", partidos_nuvem, key='sb_nuvem')
        ids_dep_partido = df_link_partido_filtrado[df_link_partido_filtrado['sgPartido'] == partido_n]['id_oficial'].astype(str).str.strip().unique()
        
        # Filtra as palavras chave dos deputados desse partido
        palavras_partido = df_temas[df_temas['id_oficial'].isin(ids_dep_partido)]['palavras_chave'].dropna()
        
        if len(palavras_partido) > 0:
            freq_partido = obter_frequencia_palavras_chave(palavras_partido)
            
            if not freq_partido.empty:
                col_nuvem_p, col_tabela_p = st.columns([0.7, 0.3])
                
                with col_nuvem_p:
                    wc = WordCloud(
                        width=900, height=500, background_color='white', 
                        colormap='tab10', max_words=80
                    ).generate_from_frequencies(freq_partido.to_dict())
                    
                    fig_d, ax = plt.subplots(figsize=(12, 6))
                    ax.imshow(wc, interpolation='bilinear')
                    ax.axis('off')
                    plt.tight_layout(pad=0)
                    st.pyplot(fig_d)
                    plt.close(fig_d)
                
                with col_tabela_p:
                    df_freq_partido = pd.DataFrame({'Palavra-chave': freq_partido.index, 'Frequência': freq_partido.values})
                    st.dataframe(df_freq_partido, hide_index=True, height=450, use_container_width=True)
            else:
                 st.warning("Não foi possível gerar a nuvem para este partido (palavras insuficientes).")
        else:
            st.warning("Nenhuma palavra-chave disponível nas proposições deste partido.")
    else:
        st.info("Nenhum partido disponível para gerar nuvem com os filtros atuais.")
st.divider()

# --- 9. P13 (TIPOS DE DESPESA) ---
st.header("📑 P13 — Tipos de Despesa (Cota Parlamentar)")
col_vazia_l, col_conteudo_p13, col_vazia_r = st.columns([0.15, 0.7, 0.15])

with col_conteudo_p13:
    tab_global, tab_individual = st.tabs(["🌎 Visão Geral (Todos no Filtro)", "👤 Visão por Deputado"])
    
    with tab_global:
        cat_data = df_filtrado.groupby('txtDescricao')['vlrLiquido'].sum().reset_index()
        if not cat_data.empty:
            fig_global = px.pie(cat_data, values='vlrLiquido', names='txtDescricao', hole=0.4, template=template_grafico, title="Distribuição de Gastos por Categoria")
            fig_global.update_layout(showlegend=True) 
            st.plotly_chart(fig_global, width='stretch')
        else:
            st.info("Nenhum dado de despesa encontrado para os filtros atuais.")

    with tab_individual:
        lista_nomes_P13 = sorted(df_filtrado['txNomeParlamentar'].dropna().unique())
        if len(lista_nomes_P13) > 0:
            dep_escolhido = st.selectbox("Selecione um deputado para análise individual de gastos:", lista_nomes_P13, key='sb_dep_p13')
            df_ind = df_filtrado[df_filtrado['txNomeParlamentar'] == dep_escolhido]
            cat_ind = df_ind.groupby('txtDescricao')['vlrLiquido'].sum().reset_index()
            
            if not cat_ind.empty:
                st.info(f"Total gasto acumulado (2023-2026) por {dep_escolhido}: **R$ {df_ind['vlrLiquido'].sum():,.2f}**")
                fig_ind = px.pie(cat_ind, values='vlrLiquido', names='txtDescricao', hole=0.4, color_discrete_sequence=px.colors.qualitative.Safe, title=f"Distribuição de Gastos de {dep_escolhido}")
                st.plotly_chart(fig_ind, width='stretch')
            else:
                 st.warning(f"O deputado {dep_escolhido} está no filtro, mas não possui registros de despesas.")
        else:
            st.warning("Nenhum deputado encontrado com os filtros atuais.")
