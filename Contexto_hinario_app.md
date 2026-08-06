# Contexto do Projeto: App Hinário Inteligente

## Visão Geral
Aplicativo mobile/desktop minimalista construído em Python (Flet) para acesso a um hinário de 601 hinos. O app vai além da leitura, oferecendo um "Agente Organizador de Cultos" (busca semântica local), opções avançadas de acessibilidade (fonte OpenDyslexic), integração de mídia (áudio/vídeo do YouTube) e modo offline (downloads locais).

## Stack Tecnológica
*   **Front-end & Roteamento:** Flet (Python)
*   **Banco de Dados:** SQLite (com tabelas normalizadas e SQLite-VSS para embeddings futuros)
*   **Gerenciamento de Mídia:** `yt-dlp` (para download e extração de áudio)
*   **Testes:** `pytest` e `pytest-asyncio` (se aplicável)

## Arquitetura de Banco de Dados (hinario_normalizado.db)
O banco de dados já foi higienizado e normalizado.
*   **Chave Surrogada:** A tabela `hino` utiliza `id` (INTEGER AUTOINCREMENT) como Primary Key. O número real do hino está na coluna `numero` (TEXT), para acomodar exceções como "587A" ou "587B".
*   **Tabelas Principais:** `hino`, `tema`, `texto_biblico`.
*   **Tabelas de Junção:** `hino_tema`, `hino_texto`.
*   **Tabelas de Usuário:** `favorito`, `historico`, `lista_culto`, `item_lista_culto`.

## Requisitos de UI/UX
*   **Minimalismo:** Design limpo, focado na legibilidade, inspirado no Material Design 3. Sem botões poluindo a tela.
*   **Acessibilidade:** Suporte nativo à troca de tamanho de fonte e uso da tipografia `OpenDyslexic`.
*   **Navegação:** 
    1. Home (Lista rolável, barra de pesquisa rápida, atalhos para Agente/Favoritos/Recentes).
    2. Tela do Hino (Letra centralizada, botões na BottomAppBar: Favoritar, Acessibilidade, Play Áudio/Vídeo, Download, Metadados).
    3. Agente Organizador (Tela de chat/input para gerar playlists baseadas em busca semântica).
    4. Pop-up/Bottom Sheet de Metadados (Autores, Texto Base e links para Textos Relacionados).

## Diretrizes de Engenharia de Software para o Assistente de IA
Este projeto deve seguir rigorosamente as melhores práticas da indústria:
1.  **Arquitetura Limpa (Clean Architecture / MVT):** Separe claramente a lógica de acesso a dados (Repository Pattern), regras de negócio (Services) e interface (Views/Flet). O código da UI não deve conter consultas SQL brutas.
2.  **Clean Code & SOLID:** Funções pequenas, nomes descritivos, responsabilidade única. Use Type Hints do Python em todos os métodos.
3.  **TDD (Test-Driven Development):** Todo core de lógica e repositórios de dados devem ser construídos com testes unitários cobrindo cenários de sucesso e falha (use `pytest`).
4.  **DevSecOps & Segurança:** Previna SQL Injection usando consultas parametrizadas (`?`). O uso do `yt-dlp` deve ser sanitizado para evitar execução de comandos arbitrários no OS.
5.  **CI/CD Mindset:** O projeto deve ser estruturado de forma que a adição de um pipeline do GitHub Actions para rodar o `pytest` e o `flake8/black` (linters) seja trivial.