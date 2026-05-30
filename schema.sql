-- Apaga as tabelas se elas já existirem para recomeçar limpo
DROP TABLE IF EXISTS VotoDeputado;
DROP TABLE IF EXISTS Votacao;
DROP TABLE IF EXISTS ProposicaoAutor;
DROP TABLE IF EXISTS Proposicao;
DROP TABLE IF EXISTS Despesa;
DROP TABLE IF EXISTS Deputado;
DROP TABLE IF EXISTS PresencaDeputado;
DROP TABLE IF EXISTS Evento;

CREATE TABLE Deputado (
    dep_id INT PRIMARY KEY,
    dep_uri VARCHAR(255) NOT NULL,
    dep_nome_civil VARCHAR(255) NOT NULL,
    dep_cpf CHAR(11),
    dep_sexo CHAR(1),
    dep_data_nascimento DATE,
    dep_escolaridade VARCHAR(100),
    dep_redes_sociais TEXT,
    dep_nome_eleitoral VARCHAR(255) NOT NULL,
    dep_url_foto VARCHAR(255)
);

CREATE TABLE Despesa (
    desp_id INTEGER PRIMARY KEY AUTOINCREMENT,
    dep_id INT,
    desp_cod_cadastro_dep INT,
    desp_nome_parlamentar VARCHAR(255),
    desp_sigla_partido VARCHAR(20),
    desp_sigla_uf CHAR(2),
    desp_nu_legislatura INT,
    desp_cod_subcota INT,
    desp_desc_subcota VARCHAR(255),
    desp_cod_especificacao INT,
    desp_desc_especificacao VARCHAR(255),
    desp_fornecedor_nome VARCHAR(255),
    desp_fornecedor_doc VARCHAR(14),
    desp_data_emissao DATE,
    desp_mes_ref INT,
    desp_ano_ref INT,
    desp_valor_bruto DECIMAL(12,2),
    desp_valor_glosa DECIMAL(12,2),
    desp_valor_liquido DECIMAL(12,2),
    desp_url_documento VARCHAR(500),
    FOREIGN KEY (dep_id) REFERENCES Deputado(dep_id)
);

CREATE TABLE Proposicao (
    prop_id INT PRIMARY KEY,
    prop_sigla_tipo VARCHAR(10),
    prop_numero INT,
    prop_ano INT,
    prop_cod_tipo INT,
    prop_desc_tipo VARCHAR(200),
    prop_ementa TEXT,
    prop_ementa_detalhada TEXT,
    prop_palavras_chave TEXT,
    prop_data_apresentacao DATE,
    prop_url_texto_integral VARCHAR(500),
    prop_ult_status_data DATETIME,
    prop_ult_status_tramitacao TEXT,
    prop_ult_status_situacao VARCHAR(200),
    prop_regime_tramitacao VARCHAR(100),
    prop_apreciacao VARCHAR(100)
);

CREATE TABLE ProposicaoAutor (
    prop_id INT,
    dep_id INT,
    autor_cod_tipo INT,
    autor_tipo_desc VARCHAR(50),
    autor_ordem_assinatura INT,
    autor_eh_proponente BOOLEAN,
    PRIMARY KEY (prop_id, dep_id),
    FOREIGN KEY (prop_id) REFERENCES Proposicao(prop_id),
    FOREIGN KEY (dep_id) REFERENCES Deputado(dep_id)
);

CREATE TABLE Votacao (
    vot_id VARCHAR(100) PRIMARY KEY,
    prop_id INT,
    evt_id INT,
    vot_data DATE,
    vot_registro DATETIME,
    vot_aprovada BOOLEAN,
    vot_total_sim INT,
    vot_total_nao INT,
    vot_total_outros INT,
    vot_descricao TEXT,
    FOREIGN KEY (prop_id) REFERENCES Proposicao(prop_id)
);

CREATE TABLE VotoDeputado (
    vot_id VARCHAR(100),
    dep_id INT,
    voto_opcao VARCHAR(50) NOT NULL,
    PRIMARY KEY (vot_id, dep_id),
    FOREIGN KEY (vot_id) REFERENCES Votacao(vot_id),
    FOREIGN KEY (dep_id) REFERENCES Deputado(dep_id)
);

CREATE TABLE Evento (
    evt_id INT PRIMARY KEY,
    evt_data DATE,
    evt_situacao VARCHAR(50),
    evt_tipo VARCHAR(100),
    evt_inicio DATETIME,
    evt_fim DATETIME,
    evt_descricao TEXT,
    evt_url_pauta VARCHAR(500)
);

CREATE TABLE PresencaDeputado (
    evt_id INT,
    dep_id INT,
    pres_data_evento DATE,
    pres_inicio_evento DATETIME,
    PRIMARY KEY (evt_id, dep_id),
    FOREIGN KEY (evt_id) REFERENCES Evento(evt_id),
    FOREIGN KEY (dep_id) REFERENCES Deputado(dep_id)
);