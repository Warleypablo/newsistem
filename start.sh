#!/bin/bash

# Obter a porta do ambiente ou usar 8000 como padrão
PORT=${PORT:-8000}

# Executar Gunicorn com configurações explícitas
exec gunicorn src.app:app \
  --bind 0.0.0.0:$PORT \
  --workers 1 \
  --timeout 120 \
  --keep-alive 2 \
  --max-requests 1000 \
  --preload