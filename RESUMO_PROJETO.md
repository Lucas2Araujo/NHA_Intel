# Resumo Geral do Projeto - Hinário Inteligente

Este documento apresenta o resumo executivo, arquitetural e técnico de tudo o que foi desenvolvido e homologado no projeto **Hinário Inteligente**.

---

## 📌 1. Visão Geral do Projeto

O **Hinário Inteligente** é uma aplicação completa e minimalista para acesso, leitura, audição e organização de um hinário de 601 hinos. Foi construído com foco em **alta performance**, **arquitetura assíncrona não-bloqueante**, **responsividade total de largura**, **acessibilidade avançada** (tamanho e 3 famílias de fontes: Padrão, Times New Roman, OpenDyslexic), **Reprodutor Interno Embutido de Áudio/Vídeo (In-App Player)**, **gerenciamento de mídia offline (`yt-dlp`)**, **Agente Organizador de Cultos (busca semântica & playlists)**, **cruzamento bíblico/temático** e **Clean Architecture com CI/CD**.

### 🛠️ Stack Tecnológica
* **Linguagem:** Python 3.14+
* **Interface Gráfica (GUI):** Flet 0.85+ (Assíncrono, Material Design 3)
* **Banco de Dados:** SQLite Assíncrono via `aiosqlite` (`hinario_normalizado.db`)
* **Gerenciamento de Mídia:** `yt-dlp` (para download e extração de áudio/vídeo)
* **Reprodutor Embutido:** In-App Player com controles de Play, Pause, Stop, barra de progresso visual e links embed
* **Inteligência Semântica:** Agente de sugestão de playlists litúrgicas por blocos
* **Testes Unitários:** `pytest` & `pytest-asyncio` (com banco em memória para isolamento - 15 testes)
* **Pipeline de CI/CD:** GitHub Actions (`.github/workflows/ci.yml`)
* **Engenharia de Software:** Clean Architecture, Repository Pattern, DTO Imutável (`frozen=True`), View Caching, Debounce de I/O, Background Tasks (`page.run_task`).

---

## 📁 2. Estrutura Completa do Projeto

```text
Hinário_App/
├── Contexto_hinario_app.md        # Documento de especificações e requisitos do projeto
├── flet_guidelines.md            # Guia de sintaxe e boas práticas do Flet 0.85+ Assíncrono
├── hinario_normalizado.db        # Banco de dados SQLite com os 601 hinos e tabelas de culto
├── main.py                       # Ponto de entrada assíncrono com injeção de repositórios, serviços e rotas
├── RESUMO_PROJETO.md             # Documentação técnica completa do projeto
├── downloads/                    # Diretório local de downloads para modo offline
├── .github/
│   └── workflows/
│       └── ci.yml                # Esteira de CI/CD para GitHub Actions
├── src/
│   ├── database/
│   │   └── connection.py         # Gerenciador de conexão assíncrona SQLite (aiosqlite)
│   ├── models/
│   │   └── hino.py               # Entidade/DTO Hino (@dataclass(frozen=True) imutável)
│   ├── repositories/
│   │   ├── hino_repository.py    # Repositório assíncrono de hinos e cruzamento de temas/bíblia
│   │   ├── favorito_repository.py# Repositório assíncrono de favoritos (tabela favorito)
│   │   ├── historico_repository.py# Repositório assíncrono de histórico (tabela historico)
│   │   └── culto_repository.py    # Repositório assíncrono de listas de culto (lista_culto)
│   ├── services/
│   │   ├── media_service.py      # Serviço assíncrono de mídia, extrator de embed e downloads yt-dlp
│   │   └── agente_service.py     # Serviço inteligente do Agente Organizador (busca semântica)
│   └── views/
│       ├── home_view.py          # View da Home (100% responsiva com atalho mágico)
│       ├── hino_view.py          # View do Hino (letra 100% largura, 3 fontes, reprodutor embutido)
│       └── agente_view.py        # View do Agente Organizador de Cultos (Novo Culto & Cultos Salvos)
└── tests/
    ├── conftest.py               # Fixtures assíncronas do pytest (banco aiosqlite em memória)
    ├── test_hino_repository.py   # Suíte de testes do repositório de hinos
    ├── test_favorito_historico_repository.py # Suíte de testes de favoritos e histórico
    ├── test_hino_view.py         # Suíte de testes unitários da HinoView
    ├── test_media_service.py     # Suíte de testes unitários do MediaService
    └── test_agente_culto_repository.py # Suíte de testes do CultoRepository e AgenteService
```

---

## ⚙️ 3. Recursos e Entregas

- **Reprodutor Interno Embutido (In-App Player):** Controles visuais de Play, Pause, Stop, barra de progresso e execução sem sair da app.
- **Extração de Embed YouTube:** Método `extract_youtube_id` e `get_embed_url`.
- **Botão "Baixar Somente Áudio (MP3)":** Download dedicado para modo 100% offline.
- **Core & Clean Architecture:** MVT assíncrono, DTO imutável, queries parametrizadas (`?`).
- **Navegação & Responsividade:** HomeView de largura total, filtro por abas, busca com debounce de 300ms.
- **Acessibilidade:** 3 famílias de fontes (Padrão, Times New Roman, OpenDyslexic) e controle de tamanho de letra.
- **Agente Organizador de Cultos:** Busca semântica por blocos litúrgicos e gerenciador de cultos salvos.
- **Cruzamento Bíblico & Temático:** Exibição de temas e textos de referência associados.
- **Integração Contínua (CI/CD):** Pipeline GitHub Actions.

---

## 🧪 4. Como Testar e Executar

### 1. Suíte de Testes Assíncronos
```bash
pytest -v
```
> **Resultado:** 15/15 testes aprovados.

### 2. Executar a Aplicação
```bash
python3 main.py
```
