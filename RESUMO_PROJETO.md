# Resumo Geral do Projeto - Hinário Inteligente

Este documento apresenta o resumo executivo, arquitetural e técnico de tudo o que foi desenvolvido e homologado no projeto **Hinário Inteligente**.

---

## 📌 1. Visão Geral do Projeto

O **Hinário Inteligente** é uma aplicação completa e minimalista para acesso, leitura, audição e organização de um hinário de 601 hinos. Foi construído com foco em **alta performance**, **arquitetura assíncrona não-bloqueante**, **responsividade total de largura**, **acessibilidade avançada** (tamanho e 3 famílias de fontes: Padrão, Times New Roman, OpenDyslexic), **Reprodutor Interno de Áudio Real (com saída física de som)**, **gerenciamento de mídia offline (`yt-dlp`)**, **Agente Organizador de Cultos (busca semântica & playlists)**, **cruzamento bíblico/temático** e **Clean Architecture com CI/CD e CD Android**.

### 🛠️ Stack Tecnológica
* **Linguagem:** Python 3.14+
* **Interface Gráfica (GUI):** Flet 0.85+ (Assíncrono, Material Design 3)
* **Banco de Dados:** SQLite Assíncrono via `aiosqlite` (`hinario_normalizado.db`)
* **Gerenciamento de Mídia:** `yt-dlp` (para download e extração de áudio/vídeo)
* **Reprodutor de Som Real:** Subprocesso nativo de reprodução de áudio (`ffplay`/`mpv`) transmitindo som real para os alto-falantes
* **Inteligência Semântica:** Agente de sugestão de playlists litúrgicas por blocos
* **Testes Unitários:** `pytest` & `pytest-asyncio` (com banco em memória para isolamento - 16 testes)
* **Esteira de CI/CD:** GitHub Actions (`.github/workflows/ci.yml` para CI e `.github/workflows/cd.yml` para Build Android APK)
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
│       ├── ci.yml                # Esteira de CI para validação de testes
│       └── cd.yml                # Esteira de CD para compilação automatizada do APK Android
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
│   │   ├── media_service.py      # Serviço assíncrono de mídia, áudio real (ffplay/mpv) e downloads yt-dlp
│   │   └── agente_service.py     # Serviço inteligente do Agente Organizador (busca semântica)
│   └── views/
│       ├── home_view.py          # View da Home (100% responsiva com atalho mágico)
│       ├── hino_view.py          # View do Hino (letra 100% largura, 3 fontes, reprodutor de som real)
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

## 🧪 3. Como Testar e Executar

### 1. Suíte de Testes Assíncronos
```bash
pytest -v
```
> **Resultado:** 16/16 testes aprovados.

### 2. Executar a Aplicação
```bash
python3 main.py
```
