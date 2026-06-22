#!/bin/bash

if [ ! -f "banco.db" ]; then
    echo "Baixando banco.db do Google Drive..."
    # Substitua a URL abaixo pelo link de compartilhamento real do seu arquivo
    gdown "https://drive.google.com/file/d/1Gh32rQd6YadaGRqwFUucWAVkD84EkXtD/view?usp=sharing" -O banco.db
    echo "Download concluído."
else
    echo "banco.db já existe."
fi

streamlit run app.py --server.port $PORT --server.address 0.0.0.0
