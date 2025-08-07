#!/bin/bash

# Define a porta padrão se não estiver definida
export PORT=${PORT:-8000}

# Inicia o Gunicorn
exec gunicorn src.app:app --bind 0.0.0.0:$PORT