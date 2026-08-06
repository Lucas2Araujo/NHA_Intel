# 🎵 Hinário Inteligente

> Aplicação desktop e web moderna, minimalista e de alta performance para consulta, leitura, reprodução de áudio/vídeo e organização litúrgica do **Hinário Adventista (601 hinos)**.

---

## 📌 Sumário
- [Visão Geral](#-visão-geral)
- [Stack Tecnológica](#-stack-tecnológica)
- [Principais Funcionalidades](#-principais-funcionalidades)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [Instalação e Execução](#-instalação-e-execução)
- [Testes e Qualidade de Código](#-testes-e-qualidade-de-código)
- [Como Subir para o GitHub](#-como-subir-para-o-github)

---

## 🚀 Visão Geral

O **Hinário Inteligente** foi desenvolvido com foco em **alta performance**, **arquitetura assíncrona não-bloqueante**, **design responsivo de largura total**, **acessibilidade avançada** e **reprodução de mídia**. 

A aplicação conta com um **Reprodutor de Áudio/Vídeo Embutido (In-App Player)**, suporte a **downloads de mídia em MP3 (modo offline)** via `yt-dlp`, um **Agente Organizador de Cultos** com sugestões semânticas por blocos litúrgicos e cruzamento bíblico/temático para cada hino.

---

## 🛠️ Stack Tecnológica

| Componente | Tecnologia | Descrição |
| :--- | :--- | :--- |
| **Linguagem** | Python 3.14+ | Core assíncrono com `async/await` nativo |
| **Interface Gráfica (GUI)** | Flet 0.85+ | Material Design 3 com suporte Desktop e Web |
| **Banco de Dados** | SQLite + `aiosqlite` | Acesso assíncrono à base parametrizada (`hinario_normalizado.db`) |
| **Gestão de Mídia** | `yt-dlp` | Download e extração de áudio/vídeo para modo offline |
| **Testes** | `pytest` & `pytest-asyncio` | Testes assíncronos isolados com banco em memória |
| **Formatação** | Black | Padronização de código conforme PEP 8 |
| **CI/CD** | GitHub Actions | Pipeline automatizada de testes contínuos (`.github/workflows/ci.yml`) |

---

## ✨ Principais Funcionalidades

### 1. 🎵 Reprodutor Embutido (In-App Player)
- Controles interativos visuais (Play, Pause, Stop, barra de progresso).
- Suporte a reprodução direta e visualização sem sair do aplicativo.

### 2. 🤖 Agente Organizador de Cultos
- Sugestão inteligente de playlists litúrgicas separadas por blocos (*Abertura*, *Oração*, *Oferta*, *Sermão*, *Encerramento*).
- Criação, salvamento e consulta de programas de culto personalizados no SQLite.

### 3. 🔍 Busca Inteligente & Navegação
- Filtro por número, título e conteúdo do hino.
- Otimização com *Debounce* de I/O (300ms) para evitar concorrência no banco.
- Abas de navegação rápida: *Todos*, *Favoritos* e *Histórico*.

### 4. 🔤 Acessibilidade Avançada
- Ajuste dinâmico de tamanho de fonte do hino.
- 3 famílias de fontes selecionáveis:
  - **Padrão** (Sans-Serif)
  - **Times New Roman** (Serif clássico)
  - **OpenDyslexic** (Fonte especializada para acessibilidade a disléxicos)

### 5. 📥 Modo Offline
- Download direto do áudio em MP3 via `yt-dlp` para execução offline local.

### 6. 📖 Cruzamento Bíblico e Temático
- Apresentação de versículos bíblicos de referência e temas associados a cada hino.

---

## 📁 Estrutura do Projeto

```text
Hinário_App/
├── .github/
│   └── workflows/
│       └── ci.yml                # Esteira de CI/CD para GitHub Actions
├── Docs/                         # Diagramas de arquitetura e casos de uso (PlantUML)
├── src/
│   ├── database/
│   │   └── connection.py         # Gerenciador de conexão assíncrona SQLite (aiosqlite)
│   ├── models/
│   │   └── hino.py               # DTO Hino (@dataclass(frozen=True))
│   ├── repositories/
│   │   ├── hino_repository.py    # Repositório assíncrono de hinos e cruzamentos
│   │   ├── favorito_repository.py# Repositório de favoritos
│   │   ├── historico_repository.py# Repositório de histórico
│   │   └── culto_repository.py    # Repositório de listas de cultos
│   ├── services/
│   │   ├── media_service.py      # Serviço de mídia e extração/download (yt-dlp)
│   │   └── agente_service.py     # Serviço inteligente do Agente de Cultos
│   └── views/
│       ├── home_view.py          # Tela principal (lista, busca, favoritos)
│       ├── hino_view.py          # Tela de detalhes do hino (letra, fontes, player)
│       └── agente_view.py        # Tela do Agente Organizador de Cultos
├── tests/                        # Suíte de testes unitários assíncronos (pytest)
│   ├── conftest.py               # Fixtures assíncronas do banco em memória
│   ├── test_hino_repository.py
│   ├── test_favorito_historico_repository.py
│   ├── test_hino_view.py
│   ├── test_media_service.py
│   └── test_agente_culto_repository.py
├── .gitignore                    # Regras de exclusão para o Git
├── hinario_normalizado.db        # Banco de dados SQLite com os 601 hinos
├── main.py                       # Ponto de entrada e roteador da aplicação Flet
├── README.md                     # Documentação oficial do repositório
└── requirements.txt              # Lista de dependências do projeto
```

---

## 📦 Instalação e Execução

### Pré-requisitos
- Python **3.14+** (ou Python 3.10+)
- `pip` e `git`

### 1. Clonar o repositório
```bash
git clone https://github.com/Lucas2Araujo/NHA_Intel.git
cd NHA_Intel
```

### 2. Criar e ativar um ambiente virtual
```bash
# Linux/macOS
python3 -m venv .venv
source .venv/bin/activate

# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Instalar as dependências
```bash
pip install -r requirements.txt
```

### 4. Executar a Aplicação
```bash
python main.py
```

---

## 🧪 Testes e Qualidade de Código

### Executar a Suíte de Testes (Pytest)
O projeto possui 100% de aprovação nos testes assíncronos:
```bash
pytest -v
```

### Formatação de Código (Black)
Para formatar o código-fonte seguindo o padrão PEP 8 / Black:
```bash
black .
```

Verificar a formatação sem alterar os arquivos:
```bash
black --check .
```

## 📄 Licença
Este projeto é de uso educacional e comunitário. Sinta-se à vontade para contribuir!
