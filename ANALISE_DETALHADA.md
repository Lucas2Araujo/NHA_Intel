# Análise Detalhada — Hinário Inteligente

> Documento gerado a partir da análise completa do código-fonte, banco de dados, testes, pipelines e documentação do repositório.

---

## 1. O que é este projeto

O **Hinário Inteligente** é uma aplicação **desktop e web** (com pipeline para **Android APK**) desenvolvida em **Python** com o framework **Flet**. Ela disponibiliza o **Hinário Adventista completo — 601 hinos** — em uma interface minimalista, escura (Material Design 3), com foco em legibilidade, performance e uso litúrgico prático.

Não é apenas um leitor de letras: o app integra **busca**, **favoritos**, **histórico de acesso**, **reprodução de áudio/vídeo**, **downloads offline**, **metadados bíblicos/temáticos** e um **Agente Organizador de Cultos** que monta playlists por blocos litúrgicos com base em um tema pastoral informado pelo usuário.

O repositório GitHub público está referenciado como `NHA_Intel` (`Lucas2Araujo/NHA_Intel`).

---

## 2. Para que foi feito

### 2.1 Contexto e público-alvo

O projeto nasceu como solução **educacional e comunitária** para igrejas e grupos que utilizam o Hinário Adventista. O objetivo central é facilitar:

| Necessidade | Como o app atende |
|---|---|
| Consultar letras durante cultos e ensaios | Lista virtualizada de 601 hinos com busca por número/título |
| Acessibilidade na leitura | Ajuste de tamanho de fonte (12–36 pt) e 3 famílias tipográficas, incluindo **OpenDyslexic** |
| Ouvir hinos durante o culto | Reprodutor interno com saída real de áudio (`ffplay`/`mpv`) e links do YouTube |
| Uso sem internet | Download de MP3 via `yt-dlp` para pasta local `downloads/` |
| Planejar ordem de culto | Agente que sugere 4 hinos organizados em blocos litúrgicos e permite salvar listas |
| Contexto teológico | Exibição de autores, texto base, temas relacionados e referências bíblicas cruzadas |

### 2.2 Requisitos de engenharia declarados

Conforme `Contexto_hinario_app.md` e `flet_guidelines.md`, o projeto foi concebido para seguir:

- **Clean Architecture / MVT** — separação entre Views, Services e Repositories
- **Repository Pattern** — toda consulta SQL isolada nos repositórios
- **SOLID e Clean Code** — funções pequenas, type hints, nomes descritivos
- **TDD** — testes unitários com `pytest` e `pytest-asyncio`
- **DevSecOps** — queries parametrizadas, sanitização de URLs, CI/CD no GitHub Actions
- **UI minimalista** — Material Design 3, sem poluição visual, bottom sheets para ações secundárias

---

## 3. Como foi feito — arquitetura geral

### 3.1 Diagrama de camadas

```text
┌─────────────────────────────────────────────────────────────┐
│                        main.py                              │
│  (Injeção de dependências, roteamento, view cache)          │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                      CAMADA DE VIEWS                        │
│  home_view.py │ hino_view.py │ agente_view.py               │
│  (Flet UI — Material Design 3, async handlers)              │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                     CAMADA DE SERVICES                      │
│  media_service.py │ agente_service.py                       │
│  (Regras de negócio: mídia, busca semântica de cultos)      │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                   CAMADA DE REPOSITORIES                    │
│  hino │ favorito │ historico │ culto                        │
│  (Acesso assíncrono ao SQLite via aiosqlite)                │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│              BANCO DE DADOS + MODELO DE DOMÍNIO             │
│  hinario_normalizado.db │ models/hino.py (DTO imutável)     │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Stack tecnológica

| Camada | Tecnologia | Versão / Detalhe |
|---|---|---|
| Linguagem | Python | 3.10+ (CI usa 3.14; CD Android usa 3.11) |
| Interface | Flet | ≥ 0.85 — async/await nativo, Flutter engine por baixo |
| Banco | SQLite + aiosqlite | Arquivo `hinario_normalizado.db` (601 hinos) |
| Mídia | yt-dlp + subprocess | Download MP3; reprodução via ffplay/mpv/paplay/aplay |
| Testes | pytest + pytest-asyncio | Banco `:memory:` isolado por fixture |
| CI | GitHub Actions | `.github/workflows/ci.yml` |
| CD Android | GitHub Actions + Flet build | `.github/workflows/cd.yml` — APK em tags `v*` |

---

## 4. Como foi feito — banco de dados

### 4.1 Modelo relacional normalizado

O banco `hinario_normalizado.db` contém **10 tabelas** (incluindo `sqlite_sequence`):

**Entidade central — `hino`**

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | INTEGER PK | Chave surrogada (AUTOINCREMENT) |
| `numero` | TEXT | Número real do hino (ex.: `"587A"`, `"587B"`) |
| `titulo` | TEXT | Título do hino |
| `letra` | TEXT | Letra completa |
| `autor_letra` | TEXT | Autor da letra |
| `autor_musica` | TEXT | Autor da música |
| `texto_base` | TEXT | Passagem bíblica base |
| `categoria` | TEXT | Categoria litúrgica |
| `subcategoria` | TEXT | Subcategoria |
| `link_video` | TEXT | URL do YouTube para áudio/vídeo |

**Relacionamentos N:N**

- `tema` ↔ `hino_tema` ↔ `hino` — temas associados a cada hino
- `texto_biblico` ↔ `hino_texto` ↔ `hino` — referências bíblicas cruzadas

**Dados de uso local**

- `favorito` — hinos marcados pelo usuário (`hino_id` PK, `data_favoritado`)
- `historico` — registro de cada visualização (`hino_id`, `data_acesso`)
- `lista_culto` — playlists salvas pelo Agente (`tema_gerador`, `data_criacao`)
- `item_lista_culto` — itens ordenados de cada lista (`lista_id`, `hino_id`, `ordem_execucao`)

### 4.2 Decisões de modelagem

- **`numero` como TEXT**, não INTEGER — permite variantes como `"587A"`/`"587B"` sem quebrar ordenação
- **Ordenação numérica** — queries usam `ORDER BY CAST(numero AS INTEGER) ASC, numero ASC`
- **Chave surrogada `id`** — rotas da UI usam `/hino/{id}`, não o número do hino
- **Preparado para embeddings futuros** — `Contexto_hinario_app.md` menciona SQLite-VSS para busca vetorial (ainda não implementado no código atual)

---

## 5. Como foi feito — camada de acesso a dados

### 5.1 `DatabaseConnection`

Gerenciador singleton de conexão assíncrona:

- Abre uma única conexão `aiosqlite` por instância
- Configura `row_factory = aiosqlite.Row` para acesso por nome de coluna
- Suporta context manager (`async with`) e banco em memória (`:memory:`) para testes

### 5.2 Repositórios

**`HinoRepository`**

- `get_all()` — lista todos os hinos (id, numero, titulo, letra)
- `get_by_id(hino_id)` — hino completo com todos os metadados
- `search(term)` — busca parametrizada com `LIKE` em numero e titulo
- `get_metadados_relacionados(hino_id)` — JOINs com `tema` e `texto_biblico`

**`FavoritoRepository`**

- `add_favorito` / `remove_favorito` — `INSERT OR IGNORE` / `DELETE`
- `is_favorito` — verificação booleana
- `get_favoritos` — JOIN com `hino`, ordenado por `data_favoritado DESC`

**`HistoricoRepository`**

- `add_acesso` — INSERT a cada abertura de hino
- `get_recentes(limit=50)` — DISTINCT com ORDER BY `data_acesso DESC`

**`CultoRepository`**

- `create_lista_culto(tema, hino_ids)` — transação: INSERT lista + N itens com `ordem_execucao`
- `get_listas_culto` — agregação com COUNT de hinos
- `get_hinos_da_lista(lista_id)` — hinos na ordem de execução

**Segurança:** todas as queries usam placeholders `?` — proteção contra SQL Injection.

### 5.3 Modelo de domínio

```python
@dataclass(frozen=True)
class Hino:
    id: Optional[int]
    numero: str
    titulo: str
    letra: Optional[str] = None
    # ... demais campos opcionais
```

DTO **imutável** (`frozen=True`) — evita mutações acidentais ao passar objetos entre camadas.

---

## 6. Como foi feito — camada de serviços

### 6.1 `MediaService`

Responsável por toda interação com mídia externa e reprodução local:

| Método | Comportamento |
|---|---|
| `_sanitize_url(url)` | Regex `^https?://...` — rejeita URLs maliciosas |
| `extract_youtube_id(url)` | Extrai ID de 11 chars de diversos formatos YouTube |
| `get_embed_url(url)` | Gera URL embed com autoplay |
| `is_downloaded(hino_id)` | Verifica existência de `downloads/hino_{id}.mp3` |
| `play_audio(source)` | Spawna subprocesso com ffplay → mpv → paplay → aplay |
| `stop_audio()` | Termina processo com `terminate()` / `kill()` |
| `get_info(url)` | Metadados via yt-dlp em `asyncio.to_thread` |
| `download_audio(hino_id, url)` | Download + conversão MP3 192kbps via FFmpegExtractAudio |

**Padrão assíncrono:** operações bloqueantes (yt-dlp, subprocess) rodam em threads via `asyncio.to_thread`, mantendo a UI responsiva.

### 6.2 `AgenteService`

Motor de sugestão de cultos — **busca semântica local** (sem LLM/API externa):

1. Recebe `tema_prompt` do usuário (ex.: "Fé e Perseverança")
2. Tokeniza palavras com `re.findall(r"\w+", prompt)` — filtra palavras ≤ 2 chars
3. Para cada palavra-chave, chama `hino_repository.search(kw)` e acumula candidatos únicos
4. Se < 4 candidatos, complementa com hinos do repositório
5. **Pontuação heurística:**
   - +5 se palavra-chave está no título
   - +2 se está em categoria/subcategoria/texto_base
6. Seleciona top 4 hinos e estrutura em **4 blocos litúrgicos:**
   - Abertura & Adoração
   - Oração & Comunhão
   - Mensagem & Edificação
   - Encerramento & Gratidão

Retorno: `{ "tema", "hinos", "blocos" }` onde cada bloco associa um hino a um momento do culto.

---

## 7. Como foi feito — interface (Views)

### 7.1 Ponto de entrada e roteamento (`main.py`)

```text
Rotas:
  /           → HomeView (lista, busca, filtros)
  /hino/{id}  → HinoView (letra, player, metadados)
  /agente     → AgenteView (organizador de cultos)
```

**Padrões implementados:**

- **View Caching** — `view_cache: Dict[str, ft.View]` reutiliza Home e Agente; HinoView é recriada a cada acesso (atualiza favorito/histórico)
- **Background tasks** — `page.run_background_task` envelopa `page.run_task` via `asyncio.wrap_future`
- **Fontes customizadas** — OpenDyslexic via CDN jsDelivr; Times New Roman nativa
- **Tema escuro** — `page.theme_mode = ft.ThemeMode.DARK` em todas as views

### 7.2 `HomeView`

- **`ft.ListView`** virtualizado para 601 hinos (performance)
- **Debounce de 300ms** na busca — cancela task anterior com `asyncio.Task.cancel()`
- **SegmentedButton** com 3 filtros: Todos | Favoritos | Recentes
- Atalho no AppBar (ícone ✨) para `/agente`
- Cada tile navega para `/hino/{id}` via `page.go()`

### 7.3 `HinoView`

Tela principal de leitura do hino:

**Ao abrir:**
1. Carrega hino por ID
2. Registra acesso no histórico
3. Busca metadados relacionados (temas + textos bíblicos)
4. Verifica estado de favorito e download offline

**BottomAppBar com 3 ações:**
- 🔤 Acessibilidade — bottom sheet com slider de tamanho (12–36 pt) e radio de fonte
- ▶️ Reprodutor — modal com play/pause/stop, barra de progresso, botões de download e abrir externo
- ⬇️ Download offline — dispara `media_service.download_audio` em background

**AppBar:**
- Voltar, título "Hino {numero}", favoritar, info (metadados)

### 7.4 `AgenteView`

Duas abas via `SegmentedButton`:

**Novo Culto**
- Campo multiline para tema pastoral
- Botão "Gerar Sugestão" → chama `agente_service.sugerir_playlist_culto`
- Exibe cards por bloco litúrgico com navegação para cada hino
- Botão "Salvar Lista" → persiste via `culto_repository.create_lista_culto`

**Cultos Salvos**
- Lista cards de cultos anteriores (tema, data, total de hinos)
- Botão play abre bottom sheet com ordem de execução

---

## 8. Como foi feito — testes

### 8.1 Infraestrutura

- **`pytest.ini`** — `asyncio_mode = auto`, escopo de fixture por função
- **`conftest.py`** — fixture `in_memory_db` cria schema completo + 3 hinos sintéticos em `:memory:`

### 8.2 Suíte de testes (22 casos)

| Arquivo | Testes | O que cobre |
|---|---|---|
| `test_hino_repository.py` | 5 | get_all, get_by_id, search, metadados, banco vazio |
| `test_favorito_historico_repository.py` | 2 | CRUD favoritos, histórico de acessos |
| `test_agente_culto_repository.py` | 2 | Criação/listagem de cultos, sugestão do agente |
| `test_media_service.py` | 6 | Sanitização URL, YouTube ID, download, play/stop, mocks yt-dlp |
| `test_hino_view.py` | 3 | Build sucesso/404, métodos de acessibilidade |
| `test_home_view.py` | 1 | Build da home view |
| `test_agente_view.py` | 1 | Build da agente view |

### 8.3 Estratégia de teste

- Repositórios testados contra banco real em memória (integração leve)
- `MediaService` usa mocks para yt-dlp e subprocess (sem I/O de rede)
- Views testadas com build assíncrono — verificam estrutura, não interação visual

---

## 9. Como foi feito — CI/CD

### 9.1 Pipeline de CI (`.github/workflows/ci.yml`)

**Trigger:** push/PR em `main` ou `master`

```
checkout → setup Python 3.14 → pip install deps → pytest -v
```

Dependências instaladas diretamente: `pytest`, `pytest-asyncio`, `aiosqlite`, `yt-dlp`, `flet`.

### 9.2 Pipeline de CD Android (`.github/workflows/cd.yml`)

**Trigger:** tags `v*` ou `workflow_dispatch`

```
checkout → Java 17 → Flutter stable → Python 3.11 → pip install → pytest → flet build apk → upload artifact → GitHub Release
```

Gera APK em `build/apk/*.apk` e publica como release quando disparado por tag.

---

## 10. Como foi feito — documentação e diagramas

A pasta `Docs/` contém diagramas **PlantUML**:

| Arquivo | Conteúdo |
|---|---|
| `DER.puml` | Diagrama Entidade-Relacionamento do SQLite |
| `Diagrama_de_Classes.puml` | Classes do sistema |
| `Diagrama_caso_de_Uso(Geral).puml` | Casos de uso gerais |
| `DCU1.puml` / `DCU2.puml` | Diagramas de casos de uso detalhados |

Documentos de referência na raiz:

- `Contexto_hinario_app.md` — especificação original e requisitos
- `flet_guidelines.md` — convenções de código Flet 0.85+ assíncrono
- `RESUMO_PROJETO.md` — resumo executivo técnico
- `README.md` — documentação pública de instalação e uso

---

## 11. Fluxos principais do usuário

### 11.1 Consultar um hino

```text
Home → digitar na busca (debounce 300ms) → clicar tile → HinoView
  → letra centralizada → ajustar fonte → favoritar → ouvir áudio
```

### 11.2 Ouvir offline

```text
HinoView → botão download → yt-dlp baixa MP3 → downloads/hino_{id}.mp3
  → reprodutor usa arquivo local em vez da URL
```

### 11.3 Montar culto

```text
Home → ícone Agente → digitar tema → "Gerar Sugestão"
  → 4 cards (blocos litúrgicos) → "Salvar Lista" → aba Cultos Salvos
```

---

## 12. Dependências (`requirements.txt`)

```
flet>=0.85.0
aiosqlite>=0.20.0
yt-dlp>=2024.0.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
```

**Dependências de sistema (opcionais, para áudio):** `ffplay` (FFmpeg), `mpv`, `paplay` ou `aplay`.

---

## 13. Pontos de atenção e limitações atuais

| Aspecto | Situação atual |
|---|---|
| Busca semântica do Agente | Heurística local por palavras-chave — não usa embeddings nem LLM |
| SQLite-VSS | Mencionado na spec, não implementado |
| Reprodução de áudio | Depende de binário externo no SO (ffplay/mpv) |
| Busca na Home | Apenas número e título — não busca no conteúdo da letra |
| HinoView | Recriada a cada navegação (correto para histórico, mas mais I/O) |
| CD Android | Requer Flutter + Java no runner; Python 3.11 (diferente do CI 3.14) |
| Formatação Black | Documentada no README, mas não está no CI nem em `requirements.txt` |

---

## 14. Como executar

```bash
# Clonar e entrar no diretório
git clone https://github.com/Lucas2Araujo/NHA_Int.git
cd NHA_Int

# Ambiente virtual
python3 -m venv .venv
source .venv/bin/activate

# Dependências
pip install -r requirements.txt

# Executar
python main.py

# Testes
pytest -v
```

---

## 15. Resumo executivo

O **Hinário Inteligente** é um app Python/Flet para consulta litúrgica do Hinário Adventista (601 hinos), construído com **Clean Architecture**, **acesso assíncrono ao SQLite**, **UI Material Design 3 responsiva** e **testes automatizados**. Foi desenvolvido para uso comunitário em igrejas, combinando leitura acessível, reprodução de mídia (online e offline), cruzamento bíblico/temático e um agente local que organiza sugestões de culto por blocos litúrgicos — tudo empacotado com CI contínuo e pipeline de build Android.
