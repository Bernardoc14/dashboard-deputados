#!/bin/bash

if [ ! -f "banco.db" ]; then
    echo "Baixando banco.db..."

    curl -L \
    "https://drive.google.com/uc?export=download&id=1Gh32rQd6YadaGRqwFUucWAVkD84EkXtD" \
    -o banco.db
fi

echo "Tamanho do banco:"
ls -lh banco.db

streamlit run app.py --server.port $PORT --server.address 0.0.0.0
