#!/bin/bash

echo "=== INFO BANCO ==="
ls -lh banco.db

echo "=== PRIMEIRAS LINHAS ==="
head -n 5 banco.db

streamlit run app.py --server.port $PORT --server.address 0.0.0.0
