# 🎵 Hinário Inteligente

<div align="center">

[![CI Test Suite](https://github.com/Lucas2Araujo/NHA_Intel/actions/workflows/ci.yml/badge.svg)](https://github.com/Lucas2Araujo/NHA_Intel/actions/workflows/ci.yml)
[![CD Android Split APKs](https://github.com/Lucas2Araujo/NHA_Intel/actions/workflows/cd.yml/badge.svg)](https://github.com/Lucas2Araujo/NHA_Intel/actions/workflows/cd.yml)
[![GitHub Release](https://img.shields.io/github/v/release/Lucas2Araujo/NHA_Intel?color=blue&label=Vers%C3%A3o&style=flat-square)](https://github.com/Lucas2Araujo/NHA_Intel/releases/latest)
[![Testes Automatizados](https://img.shields.io/badge/Testes-103%20passando-brightgreen?style=flat-square&logo=pytest&logoColor=white)](https://github.com/Lucas2Araujo/NHA_Intel/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%20%7C%203.14-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Flet 0.85+](https://img.shields.io/badge/Flet-0.85%2B-5c2d91?style=flat-square&logo=flutter&logoColor=white)](https://flet.dev/)
[![SQLite FTS5](https://img.shields.io/badge/SQLite-FTS5%20Inside-003B57?style=flat-square&logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![License: MIT](https://img.shields.io/badge/Licen%C3%A7a-MIT-green.svg?style=flat-square)](LICENSE)

> Aplicação multiplataforma (Android, Desktop e Web) moderna, minimalista e de alta performance para consulta, leitura, estudo comparativo, leitor bíblico integrado e organização litúrgica do **Hinário Adventista (Novo e Antigo)**.

---

### 📲 Baixe o Aplicativo (Última Versão)

Escolha o pacote APK correspondente à arquitetura do seu dispositivo:

[![Download ARM64](https://img.shields.io/badge/Download%20APK-ARM64--v8a%20(Smartphones%20Modernos)-2ea44f?style=for-the-badge&logo=android&logoColor=white)](https://github.com/Lucas2Araujo/NHA_Intel/releases/latest/download/Hinario_Inteligente_Android_Normal_arm64.apk)
[![Download ARMv7](https://img.shields.io/badge/Download%20APK-ARMv7%20(Aparelhos%20Legados)-f39c12?style=for-the-badge&logo=android&logoColor=white)](https://github.com/Lucas2Araujo/NHA_Intel/releases/latest/download/Hinario_Inteligente_Android_Legado_armv7.apk)
[![Download x86_64](https://img.shields.io/badge/Download%20APK-x86__64%20(Emuladores%20e%20PCs)-3498db?style=for-the-badge&logo=android&logoColor=white)](https://github.com/Lucas2Araujo/NHA_Intel/releases/latest/download/Hinario_Inteligente_Android_x86_64.apk)

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

O **Hinário Inteligente** foi concebido com foco em **alta performance**, **arquitetura assíncrona não-bloqueante**, **design responsivo**, **acessibilidade universal** e **experiência litúrgica completa**.

A aplicação integra **Busca Full-Text FTS5** insensível a acentos, **Hinário Novo (601 hinos)** e **Hinário Antigo (614 hinos)**, **Comparador Inteligente de Hinos** com visualização de diferenças verso a verso, **Bíblia Sagrada (ARA)** com parser de referências cruzadas, **Modo Escuro / Tema AMOLED**, **Agente Litúrgico de Cultos** com sugestões inteligentes e um **Sistema de Atualização Automática Integrado (OTA)** via GitHub Releases.

---

## 🛠️ Stack Tecnológica

| Camada | Tecnologia | Descrição |
| :--- | :--- | :--- |
| **Linguagem** | Python 3.11+ / 3.14 | Core assíncrono nativo com `async/await` e tipagem estática |
| **Interface (GUI)** | Flet 0.85+ | Material Design 3 responsivo com engine Flutter multiplataforma |
| **Banco de Dados** | SQLite + `aiosqlite` | Acesso não-bloqueante com virtual table **FTS5** e índices de performance |
| **Bíblia Integrada** | SQLite (ARA) | Base bíblica Almeida Revista e Atualizada para consulta imediata de versículos |
| **Comparador** | SQLite + Diff Engine | Base comparativa com mapeamento entre versões do hinário |
| **Temas & Visual** | ThemeService | Gestão de temas (Sistema, Claro, Escuro e AMOLED puro) |
| **Testes** | `pytest` & `pytest-asyncio` | 103 testes unitários e de integração com banco em memória (`:memory:`) |
| **CI/CD** | GitHub Actions | Esteira de testes contínuos e compilação automatizada de APKs Split por ABI |

---

## ✨ Principais Funcionalidades

### 1. 🔍 Busca Inteligente & Full-Text Search (FTS5)
- Tabela virtual SQLite `hino_fts` com tokenizador `unicode61 remove_diacritics 2`.
- Pesquisa instantânea por número, título, trechos da letra, autores, categorias e passagens bíblicas.
- Otimização com *Debounce* de I/O (300ms) para fluidez absoluta e ausência de concorrência.
- Navegação temática por chips clicáveis de categorias (*Adoração*, *Louvor*...) e temas (*Gratidão*, *Santidade*...).

### 2. 🔄 Comparador de Hinos (Novo vs Antigo)
- Consulta simultânea ao **Hinário Novo (601 hinos)** e ao **Hinário Antigo (614 hinos)**.
- Mapeamento direto de correspondências entre números e títulos das duas edições.
- Visualização de diferenças (*diff*) destacando estrofes idênticas, modificadas ou inéditas.

### 3. 📖 Bíblia Sagrada ARA Integrada
- Base bíblica offline completa (**Almeida Revista e Atualizada**).
- Reconhecimento automático e parser inteligente de referências bíblicas (ex: `"Sl 23:1"`, `"Jo 3:16-18"`, `"1Co 13:4-7"`).
- Modal interativo e bottom sheet para leitura imediata da passagem bíblica sem sair da tela do hino.

### 4. 🤖 Agente Litúrgico & Organizador de Cultos
- Motor semântico local que sugere playlists harmônicas estruturadas em **4 blocos litúrgicos**:
  - *Abertura & Adoração*
  - *Oração & Comunhão*
  - *Mensagem & Edificação*
  - *Encerramento & Gratidão*
- Criação, salvamento, consulta e exclusão de cultos personalizados diretamente no banco de dados.

### 5. 🌓 Tema AMOLED & Dark Mode
- Alternância instantânea de tema no cabeçalho com suporte a **Modo AMOLED** (preto puro para economia de bateria em telas OLED).
- Persistência das preferências de tema no banco de dados local.

### 6. 🔤 Acessibilidade Universal & OpenDyslexic
- Controle granular de tamanho de tipografia (12pt a 36pt).
- Suporte nativo à fonte especializada **OpenDyslexic**, auxiliando pessoas com dislexia e dificuldades de leitura.
- Persistência das preferências visuais do usuário no banco SQLite entre sessões.

### 7. 🔄 Atualizador Automático (OTA Updater)
- Verificação assíncrona em segundo plano de novas releases publicadas no repositório GitHub.
- Notificação contextual na interface com exibição de changelog formatado e download do APK da arquitetura correta.

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
│      HomeView │ HinoView │ AgenteView │ LoadingView         │
│  (Interface Flet — Material Design 3, Async Event Handlers) │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                     CAMADA DE SERVIÇOS                      │
│     AgenteService │ ThemeService │ UpdaterService           │
│  (Regras de negócio, temas, sugestão litúrgica, OTA)        │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                   CAMADA DE REPOSITÓRIOS                    │
│   Hino │ Comparativo │ Favorito │ Historico │ Culto │ Biblia│
│  (Consultas parametrizadas assíncronas via aiosqlite)       │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│              BANCO DE DADOS & MODELOS DE DOMÍNIO            │
│ hinario.db │ hinario_antigo.db │ comparativo.db │ ARA.sqlite│
└─────────────────────────────────────────────────────────────┘
```
- **DTOs Imutáveis**: Entidades modeladas com `@dataclass(frozen=True)` para garantia de previsibilidade e concorrência segura.
- **Segurança (DevSecOps)**: Todas as consultas SQL utilizam queries parametrizadas (`?`) contra injeção de SQL.
- **View Caching**: Reutilização de instâncias de views estáticas para renderização instantânea sem recriação desnecessária de componentes.


## 📁 Estrutura do Projeto

```text
Hinário_App/
├── .github/
│   └── workflows/
│       ├── ci.yml                    # Pipeline de CI (Testes pytest e contagem dinâmica)
│       └── cd.yml                    # Pipeline de CD (Build de Split APKs Android e Release)
├── assets/                           # Arquivos estáticos empacotados na aplicação
│   ├── ARA.sqlite                    # Base de dados da Bíblia Sagrada (ARA)
│   ├── hinario.db                    # Base de dados principal (Hinário Novo - 601 hinos, cultos, FTS5)
│   ├── hinario_antigo.db             # Base de dados do Hinário Antigo (614 hinos)
│   ├── hinario_comparativo.db        # Base de dados com correlação e diffs entre versões
│   ├── icon.ico                      # Ícone do aplicativo para Windows / Desktop
│   ├── icon.png                      # Ícone do aplicativo em alta resolução
│   └── fonts/                        # Tipografias para acessibilidade (OpenDyslexic)
├── Docs/                             # Documentação técnica e diagramas PlantUML
│   ├── ANALISE_DETALHADA.md          # Análise técnica aprofundada da arquitetura
│   ├── CHANGELOG_SPRINT_1.md         # Registro detalhado de sprints e evolução
│   ├── Contexto_hinario_app.md       # Especificação e requisitos do projeto
│   ├── DCU1.puml                     # Diagrama de casos de uso (Busca e Agente)
│   ├── DCU2.puml                     # Diagrama de casos de uso (Leitura, Comparativo, Bíblia)
│   ├── DER.puml                      # Diagrama Entidade-Relacionamento do banco de dados
│   ├── Diagrama_caso_de_Uso(Geral).puml # Diagrama geral de casos de uso
│   ├── Diagrama_de_Classes.puml      # Diagrama de classes da arquitetura em camadas
│   ├── flet_guidelines.md            # Guia de boas práticas e convenções Flet
│   └── RESUMO_PROJETO.md             # Resumo executivo do projeto
├── scripts/
│   └── migrate_db.py                 # Script utilitário para migrações e normalização da base
├── src/                              # Código-fonte da aplicação
│   ├── version.py                    # Versão da aplicação (injetada no CD)
│   ├── database/
│   │   └── connection.py             # Gerenciador assíncrono de conexões SQLite e FTS5
│   ├── models/
│   │   ├── biblia.py                 # DTOs de versículos e passagens bíblicas
│   │   ├── comparativo.py            # DTOs de comparação entre hinos Novo e Antigo
│   │   └── hino.py                   # DTO Hino imutável (@dataclass(frozen=True))
│   ├── repositories/
│   │   ├── biblia_repository.py      # Repositório de acesso à base da Bíblia ARA
│   │   ├── comparativo_repository.py # Repositório de busca comparativa e correlação
│   │   ├── culto_repository.py       # Repositório de persistência de listas de culto
│   │   ├── favorito_repository.py    # Repositório de gerenciamento de favoritos
│   │   ├── hino_repository.py        # Repositório de hinos, categorias e busca FTS5
│   │   └── historico_repository.py   # Repositório de histórico de acessos
│   ├── services/
│   │   ├── agente_service.py         # Motor de inteligência litúrgica por blocos
│   │   ├── theme_service.py          # Gestão de temas (Claro, Escuro, AMOLED)
│   │   └── updater_service.py        # Serviço de verificação e atualização OTA
│   └── views/
│       ├── agente_view.py            # View do Agente Litúrgico (Novo Culto e Cultos Salvos)
│       ├── hino_view.py              # View de leitura do hino, comparativo, Bíblia e fontes
│       ├── home_view.py              # View principal (busca FTS5, chips, favoritos e temas)
│       ├── loading_view.py           # View de carregamento assíncrono
│       └── update_dialog.py          # Diálogo modal de atualização do aplicativo
├── tests/                            # Suíte de testes automatizados assíncronos
│   ├── conftest.py                   # Fixtures assíncronas de banco em memória
│   ├── test_agente_culto_repository.py
│   ├── test_agente_view.py
│   ├── test_biblia_repository.py
│   ├── test_comparativo_repository.py
│   ├── test_database_connection.py
│   ├── test_favorito_historico_repository.py
│   ├── test_hino_repository.py
│   ├── test_hino_view.py
│   ├── test_home_view.py
│   ├── test_loading_view.py
│   ├── test_migration_integrity.py
│   ├── test_theme_service.py
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
O projeto conta com **103 testes assíncronos** cobrindo repositórios, serviços, views, comparador de versões, persistência e integridade do banco:
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
   - Executa a suíte completa de 103 testes unitários e de integração no ambiente Linux com Python 3.14.
   - Sincroniza dinamicamente a contagem de testes no `README.md` a cada push na branch principal.

2. **Entrega Contínua (CD - `.github/workflows/cd.yml`)**:
   - Disparada automaticamente no branch principal ou via `workflow_dispatch`.
   - Suporte a **Conventional Commits** (`feat:`, `fix:`, `perf:`, etc.) e tags SemVer (`#major`, `#minor`, `#patch`).
   - Gera notas de versão e changelog categorizados automaticamente a cada release.
   - Injeta a versão calculada em `src/version.py`, compila **Split APKs** otimizados para Android (`arm64-v8a`, `armeabi-v7a`, `x86_64`), assina com Keystore e publica automaticamente no GitHub Releases.

---

## 📄 Licença

Este projeto é distribuído sob a licença **MIT**. Consulte o arquivo [LICENSE](LICENSE) para mais informações.

Desenvolvido para fins comunitários e educacionais. Contribuições são sempre bem-vindas!

