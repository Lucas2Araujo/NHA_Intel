# 🎵 Hinário Inteligente

<div align="center">

[![CI Test Suite](https://github.com/Lucas2Araujo/NHA_Intel/actions/workflows/ci.yml/badge.svg)](https://github.com/Lucas2Araujo/NHA_Intel/actions/workflows/ci.yml)
[![CD Android Split APKs](https://github.com/Lucas2Araujo/NHA_Intel/actions/workflows/cd.yml/badge.svg)](https://github.com/Lucas2Araujo/NHA_Intel/actions/workflows/cd.yml)
[![GitHub Release](https://img.shields.io/github/v/release/Lucas2Araujo/NHA_Intel?color=blue&label=Vers%C3%A3o&style=flat-square)](https://github.com/Lucas2Araujo/NHA_Intel/releases/latest)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%20%7C%203.14-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Flet 0.85+](https://img.shields.io/badge/Flet-0.85%2B-5c2d91?style=flat-square&logo=flutter&logoColor=white)](https://flet.dev/)
[![SQLite FTS5](https://img.shields.io/badge/SQLite-FTS5%20Inside-003B57?style=flat-square&logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![License: MIT](https://img.shields.io/badge/Licen%C3%A7a-MIT-green.svg?style=flat-square)](LICENSE)

> Aplicação multiplataforma (Android, Desktop e Web) moderna, minimalista e de alta performance para consulta, leitura, reprodução de áudio/vídeo, leitor bíblico integrado e organização litúrgica do **Hinário Adventista (601 hinos)**.

---

### 📲 Baixe o Aplicativo (Última Versão)

Escolha o pacote APK correspondente à arquitetura do seu dispositivo:

[![Download ARM64](https://img.shields.io/badge/Download%20APK-ARM64--v8a%20(Smartphones%20Modernos)-2ea44f?style=for-the-badge&logo=android&logoColor=white)](https://github.com/Lucas2Araujo/NHA_Intel/releases/latest)
[![Download ARMv7](https://img.shields.io/badge/Download%20APK-ARMv7%20(Aparelhos%20Legados)-f39c12?style=for-the-badge&logo=android&logoColor=white)](https://github.com/Lucas2Araujo/NHA_Intel/releases/latest)
[![Download x86_64](https://img.shields.io/badge/Download%20APK-x86__64%20(Emuladores%20e%20PCs)-3498db?style=for-the-badge&logo=android&logoColor=white)](https://github.com/Lucas2Araujo/NHA_Intel/releases/latest)

</div>

---

## 📌 Sumário
- [Visão Geral](#-visão-geral)
- [Stack Tecnológica](#-stack-tecnológica)
- [Principais Funcionalidades](#-principais-funcionalidades)
- [Arquitetura & Engenharia de Software](#-arquitetura--engenharia-de-software)
- [Diagramas de Arquitetura (PlantUML)](#-diagramas-de-arquitetura-plantuml)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [Instalação e Execução](#-instalação-e-execução)
- [Testes e Qualidade de Código](#-testes-e-qualidade-de-código)
- [Pipeline de CI/CD](#-pipeline-de-cicd)
- [Licença](#-licença)

---

## 🚀 Visão Geral

O **Hinário Inteligente** foi concebido com foco em **alta performance**, **arquitetura assíncrona não-bloqueante**, **design responsivo em largura total**, **acessibilidade universal** e **reprodução multimídia**.

A aplicação vai além de um simples cancioneiro digital: integra **Busca Full-Text FTS5** insensível a acentos, **Bíblia Sagrada (ARA)** integrada com parser de referências cruzadas, **Reprodutor de Áudio In-App** com saída física de som (`ffplay`/`mpv`), **Gerenciador de Downloads Offline** em lote via `yt-dlp`, um **Agente Organizador de Cultos** com sugestões por blocos litúrgicos e um **Sistema de Atualização Automática Integrado (OTA)** via GitHub Releases.

---

## 🛠️ Stack Tecnológica

| Camada | Tecnologia | Descrição |
| :--- | :--- | :--- |
| **Linguagem** | Python 3.11+ / 3.14 | Core assíncrono nativo com `async/await` e tipagem estática |
| **Interface (GUI)** | Flet 0.85+ | Material Design 3 responsivo com engine Flutter multiplataforma |
| **Banco de Dados** | SQLite + `aiosqlite` | Acesso não-bloqueante com virtual table **FTS5** e índices de performance |
| **Bíblia Integrada** | SQLite (ARA) | Base bíblica Almeida Revista e Atualizada para consulta imediata de versículos |
| **Gestão de Mídia** | `yt-dlp` | Download e extração assíncrona de áudio em MP3 para modo offline |
| **Áudio Real** | Subprocess (`ffplay`/`mpv`) | Reprodutor nativo com direcionamento para alto-falantes do sistema |
| **Testes** | `pytest` & `pytest-asyncio` | 62 testes unitários e de integração com banco em memória (`:memory:`) |
| **CI/CD** | GitHub Actions | Esteira de testes contínuos e compilação automatizada de APKs Split por ABI |

---

## ✨ Principais Funcionalidades

### 1. 🔍 Busca Inteligente & Full-Text Search (FTS5)
- Tabela virtual SQLite `hino_fts` com tokenizador `unicode61 remove_diacritics 2`.
- Pesquisa instantânea por número, título, trechos da letra, autores, categorias e passagens bíblicas.
- Otimização com *Debounce* de I/O (300ms) para fluidez absoluta e ausência de concorrência.
- Navegação temática por chips clicáveis de categorias (*Adoração*, *Louvor*...) e temas (*Gratidão*, *Santidade*...).

### 2. 📖 Bíblia Sagrada ARA Integrada
- Base bíblica offline completa (**Almeida Revista e Atualizada**).
- Reconhecimento automático e parser inteligente de referências bíblicas (ex: `"Sl 23:1"`, `"Jo 3:16-18"`, `"1Co 13:4-7"`).
- Modal interativo e bottom sheet para leitura imediata da passagem bíblica sem sair da tela do hino.

### 3. 🤖 Agente Litúrgico & Organizador de Cultos
- Motor semântico local que sugere playlists harmônicas estruturadas em **4 blocos litúrgicos**:
  - *Abertura & Adoração*
  - *Oração & Comunhão*
  - *Mensagem & Edificação*
  - *Encerramento & Gratidão*
- Criação, salvamento, consulta e exclusão de cultos personalizados diretamente no banco de dados.

### 4. 🎵 Reprodutor In-App & Mídia
- Player de áudio embutido com controles (Play, Pause, Stop, barra de progresso e volume).
- Suporte a reprodução de arquivos locais baixados ou streaming via links externos do YouTube.

### 5. 📥 Gerenciador de Downloads Offline
- Rota dedicada (`/downloads`) para acompanhamento de downloads.
- Suporte a download individual por hino e download em lote para execução 100% offline.

### 6. 🔤 Acessibilidade Universal & OpenDyslexic
- Controle granular de tamanho de tipografia (12pt a 36pt).
- Suporte nativo à fonte especializada **OpenDyslexic**, auxiliando pessoas com dislexia e dificuldades de leitura.
- Persistência das preferências visuais do usuário no banco SQLite entre sessões.

### 7. 🔄 Atualizador Automático (OTA Updater)
- Verificação assíncrona em segundo plano de novas releases publicadas no repositório GitHub.
- Notificação contextual na interface com exibição de changelog e download do APK da arquitetura correta.

---

## 🏛️ Arquitetura & Engenharia de Software

O projeto segue rigorosamente os princípios de **Clean Architecture**, **SOLID** e o padrão **MVT (Model-View-Template / Repository Pattern)**:

```text
┌─────────────────────────────────────────────────────────────┐
│                          main.py                            │
│  (Roteamento assíncrono, DI, View Caching, OTA Updater)     │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                   CAMADA DE APRESENTAÇÃO                    │
│  HomeView │ HinoView │ AgenteView │ DownloadManagerView     │
│  (Interface Flet — Material Design 3, Async Event Handlers) │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                     CAMADA DE SERVIÇOS                      │
│  MediaService │ AgenteService │ UpdaterService              │
│  (Regras de negócio, streaming, sugestão litúrgica, OTA)    │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                   CAMADA DE REPOSITÓRIOS                    │
│  Hino │ Favorito │ Historico │ Culto │ Biblia               │
│  (Consultas parametrizadas assíncronas via aiosqlite)       │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│              BANCO DE DADOS & MODELOS DE DOMÍNIO            │
│  hinario.db (FTS5) │ ARA.sqlite │ Models/DTOs Imutáveis     │
└─────────────────────────────────────────────────────────────┘
```
- **DTOs Imutáveis**: Entidades modeladas com `@dataclass(frozen=True)` para garantia de previsibilidade e concorrência segura.
- **Segurança (DevSecOps)**: Todas as consultas SQL utilizam queries parametrizadas (`?`) contra injeção de SQL. Sanitização estrita de URLs para downloads.
- **View Caching**: Reutilização de instâncias de views estáticas para renderização instantânea sem recriação do DOM.


## 📁 Estrutura do Projeto

```text
Hinário_App/
├── .github/
│   └── workflows/
│       ├── ci.yml                    # Pipeline de CI (Testes com pytest no Python 3.14)
│       └── cd.yml                    # Pipeline de CD (Build de Split APKs Android e Release)
├── assets/                           # Arquivos estáticos empacotados na aplicação
│   ├── ARA.sqlite                    # Base de dados da Bíblia Sagrada (ARA)
│   ├── hinario.db                    # Base de dados principal (601 hinos, cultos, FTS5)
│   ├── icon.ico                      # Ícone do aplicativo para Windows / Desktop
│   ├── icon.png                      # Ícone do aplicativo em alta resolução
│   └── fonts/                        # Tipografias para acessibilidade (OpenDyslexic)
├── Docs/                             # Documentação técnica e diagramas PlantUML
│   ├── ANALISE_DETALHADA.md          # Análise técnica aprofundada da arquitetura
│   ├── CHANGELOG_SPRINT_1.md         # Registro detalhado de sprints e evolução
│   ├── Contexto_hinario_app.md       # Especificação e requisitos do projeto
│   ├── DCU1.puml                     # Diagrama de casos de uso (Busca e Agente)
│   ├── DCU2.puml                     # Diagrama de casos de uso (Leitura, Mídia, Bíblia)
│   ├── DER.puml                      # Diagrama Entidade-Relacionamento do banco de dados
│   ├── Diagrama_caso_de_Uso(Geral).puml # Diagrama geral de casos de uso
│   ├── Diagrama_de_Classes.puml      # Diagrama de classes da arquitetura em camadas
│   ├── flet_guidelines.md            # Guia de boas práticas e convenções Flet
│   └── RESUMO_PROJETO.md             # Resumo executivo do projeto
├── downloads/                        # Diretório local para armazenamento de áudio offline
├── scripts/
│   └── migrate_db.py                 # Script utilitário para migrações e normalização da base
├── src/                              # Código-fonte da aplicação
│   ├── version.py                    # Versão da aplicação (injetada no CD)
│   ├── database/
│   │   └── connection.py             # Gerenciador assíncrono de conexões SQLite e FTS5
│   ├── models/
│   │   ├── biblia.py                 # DTOs de versículos e passagens bíblicas
│   │   └── hino.py                   # DTO Hino imutável (@dataclass(frozen=True))
│   ├── repositories/
│   │   ├── biblia_repository.py      # Repositório de acesso à base da Bíblia ARA
│   │   ├── culto_repository.py       # Repositório de persistência de listas de culto
│   │   ├── favorito_repository.py    # Repositório de gerenciamento de favoritos
│   │   ├── hino_repository.py        # Repositório de hinos, categorias e busca FTS5
│   │   └── historico_repository.py   # Repositório de histórico de acessos
│   ├── services/
│   │   ├── agente_service.py         # Motor de inteligência litúrgica por blocos
│   │   ├── media_service.py          # Serviço de áudio real e downloads via yt-dlp
│   │   └── updater_service.py        # Serviço de verificação e atualização OTA
│   └── views/
│       ├── agente_view.py            # View do Agente Litúrgico (Novo Culto e Cultos Salvos)
│       ├── download_manager_view.py  # View do Gerenciador de Downloads Offline
│       ├── hino_view.py              # View de leitura do hino, player, Bíblia e fontes
│       ├── home_view.py              # View principal (busca FTS5, chips e filtros)
│       └── update_dialog.py          # Diálogo modal de atualização do aplicativo
├── tests/                            # Suíte de testes automatizados assíncronos
│   ├── conftest.py                   # Fixtures assíncronas de banco em memória
│   ├── test_agente_culto_repository.py
│   ├── test_agente_view.py
│   ├── test_biblia_repository.py
│   ├── test_database_connection.py
│   ├── test_favorito_historico_repository.py
│   ├── test_hino_repository.py
│   ├── test_hino_view.py
│   ├── test_home_view.py
│   ├── test_media_service.py
│   ├── test_migration_integrity.py
│   ├── test_updater_service.py
│   └── test_version.py
├── .gitignore                        # Regras de exclusão do Git
├── main.py                           # Ponto de entrada assíncrono e roteador da aplicação
├── pyproject.toml                    # Metadados do projeto e configurações de build
├── pytest.ini                        # Configurações do framework de testes pytest
├── README.md                         # Documentação principal do repositório
└── requirements.txt                  # Dependências do projeto
```

---

## 📦 Instalação e Execução

### Pré-requisitos
- **Python 3.11+** (recomendado Python 3.14)
- **Git** e **pip**
- *(Opcional para reprodução de som externo)*: `ffmpeg` / `ffplay` ou `mpv` instalado no PATH do sistema operacional.

### 1. Clonar o Repositório
```bash
git clone https://github.com/Lucas2Araujo/NHA_Intel.git
cd NHA_Intel
```

### 2. Configurar o Ambiente Virtual
```bash
# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate

# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Instalar as Dependências
```bash
pip install -r requirements.txt
```

### 4. Executar o Aplicativo
```bash
python main.py
```

---

## 🧪 Testes e Qualidade de Código

### Executar a Suíte de Testes (Pytest)
O projeto conta com **62 testes assíncronos** cobrindo repositórios, serviços, views, banco de dados e migrações:
```bash
pytest -v
```

### Formatação de Código (Black)
Para formatar o código-fonte de acordo com os padrões da PEP 8:
```bash
black .
```

Verificar a formatação sem alterar os arquivos:
```bash
black --check .
```

---

## 🚀 Pipeline de CI/CD

O repositório possui fluxos de automação contínua via **GitHub Actions**:

1. **Integração Contínua (CI - `.github/workflows/ci.yml`)**:
   - Disparada em todo `push` ou `pull_request` para as branches `main` e `master`.
   - Executa a suíte completa de 62 testes unitários e de integração no ambiente Linux com Python 3.14.

2. **Entrega Contínua (CD - `.github/workflows/cd.yml`)**:
   - Disparada automaticamente no branch principal ou via `workflow_dispatch`.
   - Calcula versão SemVer, injeta em `src/version.py`, compila **Split APKs** otimizados para Android (`arm64-v8a`, `armeabi-v7a`, `x86_64`), assina com Keystore e publica automaticamente no GitHub Releases com notas de versão.

---

## 📄 Licença

Este projeto é distribuído sob a licença **MIT**. Consulte o arquivo [LICENSE](LICENSE) para mais informações.

Desenvolvido para fins comunitários e educacionais. Contribuições são sempre bem-vindas!

