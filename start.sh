#!/bin/bash

if [ ! -f "banco.db" ]; then
    echo "banco.db não encontrado. Rodando ETL..."
    python etl_sqlite.py
    echo "ETL concluído."
else
    echo "banco.db já existe. Pulando ETL."
fi

streamlit run app.py --server.port $PORT --server.address 0.0.0.0
