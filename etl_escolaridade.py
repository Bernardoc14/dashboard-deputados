import pandas as pd
import requests
import time

def enriquecer_dados_deputados():
    print("Carregando deputados.csv...")
    df = pd.read_csv('dados/deputados.csv', sep=';', encoding='utf-8')
    
    escolaridades = []
    
    print(f"Iniciando requisições à API para {len(df)} deputados...")
    print("Isso vai levar cerca de 25 a 30 minutos. Pode deixar rodando minimizado.")
    
    for index, row in df.iterrows():
        uri = row['uri']
        
        try:
            resposta = requests.get(uri, timeout=10)
            
            if resposta.status_code == 200:
                json_retorno = resposta.json()
                dados = json_retorno.get('dados', {})
                
                escolaridade = dados.get('escolaridade')
                if not escolaridade: 
                    escolaridade = 'Não Informado'
                    
            else:
                escolaridade = f'Erro {resposta.status_code}'
                
        except Exception as e:
            escolaridade = 'Falha de Conexão'
            
        escolaridades.append(escolaridade)
        
        if (index + 1) % 50 == 0:
            print(f"{index + 1} de {len(df)} deputados processados...")
            
        time.sleep(0.2)

    df['escolaridade'] = escolaridades
    
    caminho_saida = 'dados/deputados_detalhado.csv'
    df.to_csv(caminho_saida, sep=';', index=False, encoding='utf-8-sig')
    
    print("\n" + "="*50)
    print(f"✅ Sucesso! O arquivo oficial foi gerado em: {caminho_saida}")
    print("="*50)

if __name__ == "__main__":
    enriquecer_dados_deputados()