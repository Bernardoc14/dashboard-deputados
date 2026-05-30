import sqlite3
import pandas as pd
import glob
import os

def criar_banco_de_dados():
    nome_banco = 'banco.db'
    print(f"Iniciando a criação da base de dados: {nome_banco}")
    
    conn = sqlite3.connect(nome_banco)
    cursor = conn.cursor()
    
    # ---------------------------------------------------------
    # EXECUÇÃO DO SCHEMA.SQL
    # ---------------------------------------------------------
    print("Criando tabelas a partir do schema.sql...")
    try:
        with open('schema.sql', 'r', encoding='utf-8') as f:
            script_sql = f.read()
        cursor.executescript(script_sql)
    except FileNotFoundError:
        print("ERRO: Arquivo 'schema.sql' não encontrado na pasta")
        return

    # ---------------------------------------------------------
    # 1. TABELA: Deputado 
    # ---------------------------------------------------------
    print("Carregando tabela Deputado...")
    df_dep = pd.read_csv(os.path.join('dados', 'deputados_detalhado.csv'), sep=';', encoding='utf-8', on_bad_lines='skip', engine='python')
    df_dep['id_oficial'] = df_dep['uri'].str.split('/').str[-1].str.strip().astype(str).str.split('.').str[0]
    df_dep['escolaridade'] = df_dep['escolaridade'].fillna('Não Informado')
    
    df_dep = df_dep.rename(columns={
        'id_oficial': 'dep_id',
        'uri': 'dep_uri',
        'nomeCivil': 'dep_nome_civil',
        'cpf': 'dep_cpf',
        'siglaSexo': 'dep_sexo',
        'dataNascimento': 'dep_data_nascimento',
        'escolaridade': 'dep_escolaridade',
        'urlRedeSocial': 'dep_redes_sociais',
        'nome': 'dep_nome_eleitoral',
        'urlFoto': 'dep_url_foto'
    })
    colunas_dep = [c for c in df_dep.columns if c.startswith('dep_')]
    df_dep[colunas_dep].to_sql('Deputado', conn, if_exists='append', index=False)
    
    # ---------------------------------------------------------
    # 2. TABELA: Despesa
    # ---------------------------------------------------------
    print("Carregando tabela Despesa...")
    arquivos_gastos = glob.glob(os.path.join('dados', 'Ano-*.csv'))
    df_gastos = pd.concat([pd.read_csv(f, sep=';', encoding='utf-8', on_bad_lines='skip', engine='python') for f in arquivos_gastos], ignore_index=True)
    df_gastos['dep_id'] = df_gastos['ideCadastro'].astype(str).str.split('.').str[0].str.strip()
    
    df_gastos = df_gastos.rename(columns={
        'ideCadastro': 'desp_cod_cadastro_dep',
        'txNomeParlamentar': 'desp_nome_parlamentar',
        'sgPartido': 'desp_sigla_partido',
        'sgUF': 'desp_sigla_uf',
        'nuLegislatura': 'desp_nu_legislatura',
        'numSubCota': 'desp_cod_subcota',
        'txtDescricao': 'desp_desc_subcota',
        'numEspecificacaoSubCota': 'desp_cod_especificacao',
        'txtDescricaoEspecificacao': 'desp_desc_especificacao',
        'txtFornecedor': 'desp_fornecedor_nome',
        'txtCNPJCPF': 'desp_fornecedor_doc',
        'datEmissao': 'desp_data_emissao',
        'numMes': 'desp_mes_ref',
        'numAno': 'desp_ano_ref',
        'vlrDocumento': 'desp_valor_bruto',
        'vlrGlosa': 'desp_valor_glosa',
        'vlrLiquido': 'desp_valor_liquido',
        'urlDocumento': 'desp_url_documento'
    })
    colunas_desp = ['dep_id'] + [c for c in df_gastos.columns if c.startswith('desp_')]
    df_gastos[colunas_desp].to_sql('Despesa', conn, if_exists='append', index=False)

    # ---------------------------------------------------------
    # 3. TABELA: Proposicao
    # ---------------------------------------------------------
    print("Carregando tabela Proposicao...")
    arquivos_prop = glob.glob(os.path.join('dados', 'proposicoes-*.csv'))
    if arquivos_prop:
        df_prop = pd.concat([pd.read_csv(f, sep=';', encoding='utf-8', on_bad_lines='skip', engine='python') for f in arquivos_prop], ignore_index=True)
        col_ementa = next((col for col in df_prop.columns if 'ementa' in col.lower()), None)
        col_id = next((col for col in df_prop.columns if col.lower() in ['id', 'idproposicao', 'id_proposicao']), None)
        
        if col_ementa and col_id:
            df_prop['prop_ementa'] = df_prop[col_ementa].astype(str).str.replace('"', '')
            df_prop['prop_id'] = df_prop[col_id].astype(str).str.split('.').str[0].str.strip()
            
            df_prop = df_prop.rename(columns={
                'siglaTipo': 'prop_sigla_tipo',
                'numero': 'prop_numero',
                'ano': 'prop_ano',
                'codTipo': 'prop_cod_tipo',
                'descricaoTipo': 'prop_desc_tipo',
                'ementaDetalhada': 'prop_ementa_detalhada',
                'keywords': 'prop_palavras_chave',
                'dataApresentacao': 'prop_data_apresentacao',
                'urlInteiroTeor': 'prop_url_texto_integral',
                'ultimoStatus_dataHora': 'prop_ult_status_data',
                'ultimoStatus_descricaoTramitacao': 'prop_ult_status_tramitacao',
                'ultimoStatus_descricaoSituacao': 'prop_ult_status_situacao',
                'ultimoStatus_regime': 'prop_regime_tramitacao',
                'ultimoStatus_apreciacao': 'prop_apreciacao'
            })
            colunas_prop = [c for c in df_prop.columns if c.startswith('prop_')]
            df_prop[colunas_prop].to_sql('Proposicao', conn, if_exists='append', index=False)

    # ---------------------------------------------------------
    # 4. TABELA: ProposicaoAutor
    # ---------------------------------------------------------
    print("Carregando tabela ProposicaoAutor...")
    arquivos_autores = glob.glob(os.path.join('dados', 'proposicoesAutores-*.csv'))
    if arquivos_autores:
        df_autores = pd.concat([pd.read_csv(f, sep=';', encoding='utf-8', on_bad_lines='skip', engine='python') for f in arquivos_autores], ignore_index=True)
        df_autores['dep_id'] = df_autores['idDeputadoAutor'].astype(str).str.split('.').str[0].str.strip()
        df_autores['prop_id'] = df_autores['idProposicao'].astype(str).str.split('.').str[0].str.strip()
        
        df_autores = df_autores.rename(columns={
            'codTipoAutor': 'autor_cod_tipo',
            'tipoAutor': 'autor_tipo_desc',
            'ordemAssinatura': 'autor_ordem_assinatura',
            'proponente': 'autor_eh_proponente'
        })
        colunas_autores = ['prop_id', 'dep_id'] + [c for c in df_autores.columns if c.startswith('autor_')]
        df_autores = df_autores[colunas_autores].drop_duplicates(subset=['prop_id', 'dep_id'])
        df_autores.to_sql('ProposicaoAutor', conn, if_exists='append', index=False)

    # ---------------------------------------------------------
    # 5. TABELA: Votacao
    # ---------------------------------------------------------
    print("Carregando tabela Votacao...")
    arquivos_votacoes = glob.glob(os.path.join('dados', 'votacoes-*.csv'))
    if arquivos_votacoes:
        df_votacoes = pd.concat([pd.read_csv(f, sep=';', encoding='utf-8', on_bad_lines='skip', engine='python') for f in arquivos_votacoes], ignore_index=True)
        df_votacoes['prop_id'] = df_votacoes['ultimaApresentacaoProposicao_idProposicao'].astype(str).str.split('.').str[0].str.strip()
        
        df_votacoes = df_votacoes.rename(columns={
            'id': 'vot_id',
            'data': 'vot_data',
            'dataHoraRegistro': 'vot_registro',
            'idEvento': 'evt_id',
            'aprovacao': 'vot_aprovada',
            'votosSim': 'vot_total_sim',
            'votosNao': 'vot_total_nao',
            'votosOutros': 'vot_total_outros',
            'descricao': 'vot_descricao'
        })
        colunas_votacao = ['prop_id', 'evt_id'] + [c for c in df_votacoes.columns if c.startswith('vot_')]
        df_votacoes = df_votacoes[colunas_votacao].drop_duplicates(subset=['vot_id'])
        df_votacoes.to_sql('Votacao', conn, if_exists='append', index=False)

    # ---------------------------------------------------------
    # 6. TABELA: VotoDeputado
    # ---------------------------------------------------------
    print("Carregando tabela VotoDeputado...")
    arquivos_votos = glob.glob(os.path.join('dados', 'votacoesVotos-*.csv'))
    if arquivos_votos:
        df_votos = pd.concat([pd.read_csv(f, sep=';', encoding='utf-8', on_bad_lines='skip', engine='python') for f in arquivos_votos], ignore_index=True)
        df_votos['dep_id'] = df_votos['deputado_id'].astype(str).str.split('.').str[0].str.strip()
        
        df_votos = df_votos.rename(columns={
            'idVotacao': 'vot_id',
            'voto': 'voto_opcao'
        })
        
        df_votos = df_votos.dropna(subset=['voto_opcao'])
        
        colunas_votos = ['vot_id', 'dep_id', 'voto_opcao']
        df_votos = df_votos[colunas_votos].drop_duplicates(subset=['vot_id', 'dep_id'])
        df_votos.to_sql('VotoDeputado', conn, if_exists='append', index=False)

    # ---------------------------------------------------------
    # 7. TABELAS: Evento e PresencaDeputado
    # ---------------------------------------------------------
    print("Carregando tabelas Evento e PresencaDeputado...")
    arquivos_presenca = glob.glob(os.path.join('dados', 'eventosPresencaDeputados-*.csv'))
    
    if arquivos_presenca:
        df_pres = pd.concat([pd.read_csv(f, sep=';', encoding='utf-8', on_bad_lines='skip', engine='python') for f in arquivos_presenca], ignore_index=True)
        
        df_pres['dep_id'] = df_pres['idDeputado'].astype(str).str.split('.').str[0].str.strip()
        df_pres['evt_id'] = df_pres['idEvento'].astype(str).str.split('.').str[0].str.strip()

        df_evento = pd.DataFrame({'evt_id': df_pres['evt_id'].unique()})
        df_evento.to_sql('Evento', conn, if_exists='append', index=False)

        if 'dataHoraInicio' in df_pres.columns:
            df_pres = df_pres.rename(columns={'dataHoraInicio': 'pres_inicio_evento'})
            df_pres['pres_data_evento'] = df_pres['pres_inicio_evento'].str[:10]
        elif 'data' in df_pres.columns:
            df_pres = df_pres.rename(columns={'data': 'pres_data_evento'})
            
        colunas_pres = [c for c in df_pres.columns if c in ['evt_id', 'dep_id', 'pres_data_evento', 'pres_inicio_evento']]
        df_pres = df_pres[colunas_pres].drop_duplicates(subset=['evt_id', 'dep_id'])
        df_pres.to_sql('PresencaDeputado', conn, if_exists='append', index=False)

    conn.close()
    print("Base de dados gerada.")

if __name__ == "__main__":
    criar_banco_de_dados()