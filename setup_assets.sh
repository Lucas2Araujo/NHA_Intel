#!/bin/bash
# Script de setup para a pasta assets
# Execute na raiz do projeto: bash setup_assets.sh

set -e

echo "=== Setup da pasta assets ==="

# Criar diretório assets se não existir
mkdir -p assets

# Copiar banco de dados
if [ -f "hinario_normalizado.db" ]; then
    cp hinario_normalizado.db assets/
    echo "✅ Banco de dados copiado para assets/"
else
    echo "❌ Erro: hinario_normalizado.db não encontrado na raiz do projeto"
    exit 1
fi

# Copiar ícone do aplicativo
if [ -f "icon.ico" ]; then
    cp icon.ico assets/
    echo "✅ Ícone do aplicativo (icon.ico) copiado para assets/"
fi

echo "=== Setup concluído ==="
echo ""
echo "Para rodar os testes:"
echo "  python -m pytest -v"
echo ""
echo "Para rodar o app:"
echo "  python main.py"
