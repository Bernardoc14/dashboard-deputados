import streamlit as st
import pandas as pd
import plotly.express as px
import os
import glob
from wordcloud import WordCloud
import matplotlib.pyplot as plt

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Dashboard Legislativo 2023-2026", page_icon="🏛️", layout="wide")
template_grafico = "plotly_white"

@st.cache_data
def carregar_tudo():
    # A. GASTOS + PERFIL (P1, P4, P13)
    arquivos_gastos = glob.glob(os.path.join('dados', 'Ano-*.csv'))
    df_gastos = pd.concat([pd.read_csv(f, sep=';', encoding='utf-8', low_memory=False) for f in arquivos_gastos], ignore_index=True)
    
    # Padroniza ideCadastro removendo ponto flutuante (.0) e espaços
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
    df_autores = pd.concat([pd.read_csv(f, sep=';', encoding='utf-8') for f in arquivos_autores], ignore_index=True)
    
    # PADRONIZAÇÃO CRÍTICA: Transforma os IDs de Autores em texto limpo sem ".0"
    df_autores['id_oficial'] = df_autores['idDeputadoAutor'].astype(str).str.split('.').str[0].str.strip()
    df_autores['idProposicao_link'] = df_autores['idProposicao'].astype(str).str.split('.').str[0].str.strip()
    
    # D. EMENTAS PARA NUVEM (P11d)
    arquivos_prop = glob.glob(os.path.join('dados', 'proposicoes-*.csv'))
    lista_prop = []
    for f in arquivos_prop:
        try:
            df_temp = pd.read_csv(f, sep=';', encoding='utf-8', on_bad_lines='skip')
            lista_prop.append(df_temp)
        except Exception as e:
            print(f"Erro ao tentar ler o arquivo {f}: {e}")
            
    if lista_prop:
        df_prop = pd.concat(lista_prop, ignore_index=True)
        
        col_ementa = next((col for col in df_prop.columns if 'ementa' in col.lower()), None)
        col_id = next((col for col in df_prop.columns if col.lower() in ['id', 'idproposicao', 'id_proposicao']), None)
        
        if col_ementa and col_id:
            df_prop['ementa'] = df_prop[col_ementa].astype(str).str.replace('"', '')
            df_prop['idProposicao_link'] = df_prop[col_id].astype(str).str.split('.').str[0].str.strip()

            col_keywords = next((col for col in df_prop.columns if 'keyword' in col.lower()), None)
            colunas_prop = ['idProposicao_link', 'ementa']
            if col_keywords:
                colunas_prop.append(col_keywords)
                df_prop = df_prop.rename(columns={col_keywords: 'keywords'})

            df_temas = pd.merge(
                df_autores[['idProposicao_link', 'id_oficial']],
                df_prop[colunas_prop],
                on='idProposicao_link',
                how='inner'
            )
            if 'keywords' not in df_temas.columns:
                df_temas['keywords'] = ''
        else:
            df_temas = pd.DataFrame(columns=['idProposicao_link', 'id_oficial', 'ementa', 'keywords'])
    else:
        df_temas = pd.DataFrame(columns=['idProposicao_link', 'id_oficial', 'ementa', 'keywords'])

    # E. CLASSIFICAÇÃO TEMÁTICA (P2)
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
        texto = (str(row.get('keywords', '')) + ' ' + str(row.get('ementa', ''))).lower()
        scores = {tema: sum(1 for p in palavras if p in texto) for tema, palavras in TEMAS_KEYWORDS.items()}
        scores = {k: v for k, v in scores.items() if v > 0}
        return max(scores, key=scores.get) if scores else None

    if not df_temas.empty:
        df_temas['tema'] = df_temas.apply(classificar_tema, axis=1)
        df_temas_classificado = df_temas.dropna(subset=['tema'])
    else:
        df_temas_classificado = pd.DataFrame(columns=['idProposicao_link', 'id_oficial', 'ementa', 'keywords', 'tema'])

    return df_principal, frequencia_partido, df_autores, df_temas, df_temas_classificado, TEMAS_KEYWORDS

# --- EXECUÇÃO DO CARREGAMENTO ---
df_principal, df_freq, df_autores, df_temas, df_temas_classificado, TEMAS_KEYWORDS = carregar_tudo()

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

# --- SEÇÃO P2 (AGRUPAMENTO TEMÁTICO) ---
st.header("🗂️ P2 — Agrupamento por Eixo Temático de Atuação")

if df_temas_classificado.empty:
    st.warning("Nenhuma proposição classificada encontrada. Verifique se os arquivos proposicoes-*.csv estão na pasta dados/.")
else:
    # Montar perfil temático por deputado (todos os temas, não só o dominante)
    ids_filtrados = df_filtrado['id_oficial'].unique()
    df_tc_filtrado = df_temas_classificado[df_temas_classificado['id_oficial'].isin(ids_filtrados)]

    # Contagem de proposições por deputado+tema
    perfil_dep = df_tc_filtrado.groupby(['id_oficial', 'tema']).size().reset_index(name='qtd')
    # Tema dominante de cada deputado
    idx_max = perfil_dep.groupby('id_oficial')['qtd'].idxmax()
    tema_dominante = perfil_dep.loc[idx_max][['id_oficial', 'tema']].rename(columns={'tema': 'tema_dominante'})

    # Contagem de deputados por tema dominante
    contagem_temas = tema_dominante['tema_dominante'].value_counts().reset_index()
    contagem_temas.columns = ['Tema', 'Deputados']

    # Contagem de proposições por tema (para o gráfico de barras)
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
        fig_p2a.update_layout(
            yaxis={'categoryorder': 'total ascending'},
            showlegend=False,
            height=450,
            bargap=0.3,
            margin=dict(l=20, r=20, t=50, b=20),
        )
        fig_p2a.update_traces(textposition='outside', cliponaxis=False)
        st.plotly_chart(fig_p2a, use_container_width=True)

    with tab_p2b:
        fig_p2b = px.bar(
            contagem_temas.sort_values('Deputados'), x='Deputados', y='Tema', orientation='h',
            color='Tema', color_discrete_map=CORES_TEMAS,
            text_auto=True, template=template_grafico,
            title="Número de deputados cujo tema principal de atuação é cada eixo"
        )
        fig_p2b.update_layout(
            yaxis={'categoryorder': 'total ascending'},
            showlegend=False,
            height=450,
            bargap=0.15,
            bargroupgap=0.05,
            margin=dict(l=20, r=60, t=50, b=20),
        )
        fig_p2b.update_traces(
            texttemplate='%{x}',
            textposition='outside',
            cliponaxis=False,
            insidetextanchor='middle',
        )
        st.plotly_chart(fig_p2b, use_container_width=True)

        st.subheader("Lista de Deputados por Tema Dominante")
        tema_filtro = st.selectbox("Selecione o tema:", sorted(contagem_temas['Tema'].tolist()), key='tema_lista')
        deps_tema = tema_dominante[tema_dominante['tema_dominante'] == tema_filtro]['id_oficial'].tolist()
        # Buscar nomes
        nomes_tema = df_filtrado[df_filtrado['id_oficial'].isin(deps_tema)][['txNomeParlamentar','sgPartido','sgUF']].drop_duplicates().sort_values('txNomeParlamentar').reset_index(drop=True)
        nomes_tema.columns = ['Nome', 'Partido', 'UF']
        st.caption(f"{len(nomes_tema)} deputado(s) com tema dominante: **{tema_filtro}**")
        st.dataframe(nomes_tema, use_container_width=True, hide_index=True)

    with tab_p2c:
        lista_deps_p2 = sorted(df_filtrado['txNomeParlamentar'].dropna().unique())
        dep_p2 = st.selectbox("Selecione o deputado:", lista_deps_p2, key='dep_p2')
        id_dep_p2 = df_filtrado[df_filtrado['txNomeParlamentar'] == dep_p2]['id_oficial'].iloc[0] if not df_filtrado[df_filtrado['txNomeParlamentar'] == dep_p2].empty else None

        if id_dep_p2:
            perfil_ind = df_temas_classificado[df_temas_classificado['id_oficial'] == id_dep_p2]['tema'].value_counts().reset_index()
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
            'à', 'às', 'aquele', 'aquela',
            'lei', 'altera', 'dispõe', 'institui', 'cria', 'art', 'projeto', 'requerimento', 'requer',
            'parecer', 'pauta', 'comissão', 'retirada', 'matéria', 'moção', 'louvor', 'prestados',
            'regozijo', 'nominal', 'realização', 'excelentes', 'substitutivo', 'ric', 'exarado',
            'adiamento', 'outras', 'pdl', 'termo', 'termos', 'dep', 'uor',
            'público', 'pública', 'públicos', 'públicas', 'fim', 'fins', 'acerca', 'objeto', 'âmbito',
            'pl', 'sr', 'sra', 'srª', 'srs', 'voto', 'votos', 'convida',
            'determina', 'manifesta', 'manifestação', 'encaminha', 'reitera', 'indica', 'indicação',
            'proíbe', 'torna', 'obriga', 'concede', 'autoriza', 'autorização', 'instituído', 'criado',
            'alterado', 'destinado', 'fixa', 'senhor', 'senhora', 'silva', 'santos', 'oliveira',
            'souza', 'melo', 'outros', 'bancada', 'partido', 'liderança', 'líder', 'bloco', 'membro',
            'membros', 'visto', 'ter', 'haver', 'meio', 'forma', 'efeito', 'caso', 'prazo',
            'dia', 'dias', 'ano', 'anos', 'data', 'janeiro', 'fevereiro', 'março', 'abril', 'maio',
            'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro', 'brasil',
            'república', 'ccjc', 'cft', 'ccj', 'sgt', 'plen', 'avulso', 'pec', 'plp',
            'mpv', 'inc', 'rpd', 'prl', 'par', 'n', 'nº', 'dá', 'sem',
            'nacional', 'federal', 'estadual', 'municipal', 'deputado', 'câmara', 'senado',
            'congresso', 'mesa', 'plenário', 'regime', 'urgência', 'urgente', 'decreto',
            'estabelece', 'adotado', 'solene', 'dispor', 'convocação', 'votação', 'aprovação',
            'providências', 'informações', 'relator', 'relatora', 'artigo', 'proposição',
            'solicita', 'sugere', 'debater', 'discussão', 'audiência', 'redação', 'apreciação',
            'emenda', 'adoção', 'inclusão', 'ato', 'legislativa',
        }
        tema_nuvem = st.selectbox("Selecione o eixo temático:", sorted(TEMAS_KEYWORDS.keys()), key='tema_nuvem')

        ementas_tema = df_tc_filtrado[df_tc_filtrado['tema'] == tema_nuvem]['ementa'].dropna()
        if len(ementas_tema) == 0:
            st.warning("Nenhuma ementa encontrada para este tema com os filtros atuais.")
        else:
            texto_tema = " ".join(ementas_tema.astype(str)).lower()
            texto_tema = " ".join(texto_tema.split())
            try:
                wc_tema = WordCloud(
                    width=1400, height=600,
                    background_color='white',
                    stopwords=ruido_nuvem,
                    colormap='tab10',
                    min_font_size=10,
                    max_words=80,
                    collocations=False,
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

# --- SEÇÃO P4 (ESCOLARIDADE) ---
st.header("🎓 P4 — Perfil por Escolaridade")
df_u = df_filtrado.drop_duplicates(subset=['id_oficial'])
esc_data = df_u['escolaridade'].value_counts().reset_index()
esc_data.columns = ['Escolaridade', 'Qtd']

fig_p4 = px.bar(esc_data, x='Qtd', y='Escolaridade', orientation='h', color='Qtd', color_continuous_scale='Blues', text_auto=True, template=template_grafico)
fig_p4.update_layout(yaxis={'categoryorder':'total ascending'})
st.plotly_chart(fig_p4, use_container_width=True)

escolaridades_disp = esc_data['Escolaridade'].tolist()
esc_sel = st.selectbox("Ver deputados por escolaridade:", escolaridades_disp, key='esc_sel')
deps_esc = df_u[df_u['escolaridade'] == esc_sel][['txNomeParlamentar', 'sgPartido', 'sgUF']].drop_duplicates().sort_values('txNomeParlamentar').reset_index(drop=True)
deps_esc.columns = ['Nome', 'Partido', 'UF']
st.caption(f"{len(deps_esc)} deputado(s) com escolaridade: **{esc_sel}**")
st.dataframe(deps_esc, use_container_width=True, hide_index=True)

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
        
        # 1. Isolar os IDs dos deputados do partido selecionado e garantir que são strings limpas
        df_link_partido = df_filtrado[['id_oficial', 'sgPartido']].drop_duplicates()
        ids_dep = df_link_partido[df_link_partido['sgPartido'] == partido_n]['id_oficial'].astype(str).str.strip().unique()
        
        # 2. Garantir que o ID do deputado na tabela de temas também é string limpa para o cruzamento funcionar
        df_temas_copia = df_temas.copy()
        df_temas_copia['id_oficial'] = df_temas_copia['id_oficial'].astype(str).str.strip()
        
        # 3. Filtrar as ementas pertencentes a estes IDs
        ementas_partido = df_temas_copia[df_temas_copia['id_oficial'].isin(ids_dep)]['ementa'].dropna()
        
        # --- PRINTS DE DIAGNÓSTICO NO TERMINAL ---
        print(f"\n--- DIAGNÓSTICO STREAMLIT ({partido_n}) ---")
        print(f"IDs de deputados do partido: {len(ids_dep)}")
        print(f"Total de linhas em df_temas: {len(df_temas_copia)}")
        print(f"Ementas encontradas após o filtro do partido: {len(ementas_partido)}")
        # ----------------------------------------

        # 4. Juntar tudo, forçar minúsculo e limpar espaços/quebras de linha repetidas
        texto = " ".join(ementas_partido.astype(str)).lower()
        texto = " ".join(texto.split()) # Remove quebras de linha (\n) e espaços duplos
        
        # 5. Limpeza cirúrgica de termos curtinhos direto na string
        termos_para_remover = [' pl ', ' sr ', ' sra ', ' à ', ' nº ', ' art ', 'dá', 'sem']
        for termo in termos_para_remover:
            texto = texto.replace(termo, ' ')
        
        # 6. Super lista de Stopwords importada do teste.py
        ruido_legislativo = {
            'da', 'n', 'dá', 'do', 'que', 'em', 'para', 'um', 'uma', 'os', 'as', 'ao', 'aos', 'com', 'por', 'pela', 'pelo', 'dos', 'das', 'pelos', 'pelas', 'nos', 'nas', 'sob', 'sobre', 'como', 'na', 'no', 'ou', 'se', 'o', 'a', 'e', 'de', 'através', 'seu', 'sua', 'deste', 'desta', 'à', 'às', 'aquele', 'aquela', 'lei', 'altera', 'dispõe', 'institui', 'cria', 'nº', 'art', 
            'parágrafo', 'inciso', 'projeto', 'requerimento', 'requer', 'parecer', 'pauta', 'comissão','retirada', 'matéria', 'moção', 'louvor', 'prestados', 'regozijo', 'nominal','realização', 'excelentes',
            'substitutivo', 'ric', 'exarado', 'adiamento', 'outras', 'pdl', 'termo', 'termos', 'dep',
            'uor',
            'público', 'pública', 'públicos', 'públicas', 'fim', 'fins', 'acerca', 'objeto', 'âmbito',
            'pl', 'sr', 'srª', 'sra', 'srs', 'voto', 'votos', 'convida', 
            'determina', 'manifesta', 'manifestação', 'encaminha', 'reitera', 'indica', 'indicação', 
            'proíbe', 'torna', 'obriga', 'concede', 'autoriza', 'autorização', 'instituído', 'criado', 
            'alterado', 'destinado', 'fixa', 'senhor', 'senhora', 'silva', 'santos', 'oliveira', 
            'souza', 'melo', 'outros', 'bancada', 'partido', 'liderança', 'líder', 'bloco', 'membro', 
            'membros', 'visto', 'ter', 'haver', 'fim', 'meio', 'forma', 'efeito', 'caso', 'prazo', 
            'dia', 'dias', 'ano', 'anos', 'data', 'janeiro', 'fevereiro', 'março', 'abril', 'maio', 
            'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro', 'brasil', 
            'republic', 'república', 'ccjc', 'cft', 'ccj', 'sgt', 'plen', 'avulso', 'pec', 'plp', 
            'mpv', 'inc', 'rpd', 'prl', 'par'
        }
        texto_limpo = texto.strip()
        
        # Se após limpar tudo sobrarem palavras, renderiza o gráfico
        if len(texto_limpo) > 5:
            try:
                wc = WordCloud(
                    width=1400,
                    height=700,
                    background_color='white',
                    stopwords=ruido_legislativo,
                    colormap='tab10',
                    min_font_size=10,
                    max_words=70,
                    collocations=False,
                    regexp=r"\b[a-zA-ZáéíóúçãõâêôàÀíÍóÓúÚáÁéÉãÃõÕçÇ]+\b"
                ).generate(texto_limpo)
                
                fig_d, ax = plt.subplots(figsize=(14, 7))
                ax.imshow(wc, interpolation='bilinear')
                ax.axis('off')
                plt.tight_layout(pad=0)
                
                st.pyplot(fig_d)
                plt.close(fig_d) 
            except ValueError:
                st.info("As ementas deste partido contêm apenas jargões técnicos que foram totalmente filtrados.")
        else:
            st.warning("Pouco texto disponível para gerar a nuvem deste partido após a filtragem de ruídos.")
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
