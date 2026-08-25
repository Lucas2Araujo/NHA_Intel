# Changelog — Sprint 1 & 2: Bug Fixes + Busca Real + Polimento v0.2

> Documento gerado automaticamente com todas as alterações implementadas nas Sprints 1 e 2 e roadmap futuro.

---

## 📅 Data: 2026-08-07

## 🎯 Resumo da Sprint 2 — Busca Real + Polimento (Concluída)

Nesta sprint focamos em transformar a busca e a usabilidade do aplicativo com **FTS5 Full-Text Search**, navegação por categorias/temas, persistência de preferências e otimizações de banco de dados.

### ⚡ 1. Busca Full-Text com FTS5 (SQLite)
- **Tabela Virtual `hino_fts`**: Criada via `connection.py` com tokenizador `unicode61 remove_diacritics 2` para busca insensível a acentos.
- **Busca Abrangente**: A barra de pesquisa agora busca por números, títulos, palavras na letra, categorias, subcategorias e textos base bíblicos.
- **Fallback Seguro**: Se o FTS5 por algum motivo falhar ou não estiver disponível, o sistema faz fallback gracioso para a query `LIKE` parametrizada.

### 📂 2. Aba "Explorar" por Categorias e Temas
- **Navegação Temática**: Nova aba **Explorar** no `SegmentedButton` da `HomeView`.
- **Chips Clicáveis**: Exibe chips das categorias ("Adoração", "Louvor"...) e dos temas ("Santidade", "Gratidão"...).
- **Filtro Automático**: Ao clicar em qualquer chip, o app filtra instantaneamente a lista de hinos associados.

### 🏷️ 3. Chips Clicáveis no Modal de Info do Hino
- **Navegação Cruzada**: No modal de informações da `HinoView`, a categoria, temas e textos bíblicos agora são exibidos como chips coloridos e clicáveis.
- **Busca por Rota**: Clicar em um chip fecha o modal e redireciona automaticamente para a Home filtrando os hinos daquele tema (`/?q=termo`).

### 🔧 4. Índices SQL & Performance
- **7 Índices Criados**:
  - `idx_historico_hino_data` (historico)
  - `idx_favorito_data` (favorito)
  - `idx_hino_numero` (hino)
  - `idx_hino_titulo` (hino)
  - `idx_hino_tema_hino` / `idx_hino_tema_tema` (hino_tema)
  - `idx_hino_texto_hino` (hino_texto)
- **Limpeza Automática de Histórico**: Registros de histórico com mais de 90 dias são removidos automaticamente no startup.

### 🎨 5. Melhorias de UX e Acessibilidade
- **Loading State**: `ProgressRing` amigável enquanto a lista de 601 hinos é carregada no primeiro boot.
- **Empty States Ilustrados**: Telas de Favoritos vazios, Recentes vazios e Busca sem resultados agora contam com ícones, mensagens explicativas e dicas de uso.
- **Labels na BottomAppBar**: Textos descritivos ("Fonte", "Mídia", "Download") adicionados abaixo dos ícones da barra inferior da `HinoView`.
- **Persistência de Preferências**: O tamanho e a família de fonte (OpenDyslexic, Times New Roman, Padrão) ajustados pelo usuário agora são salvos na tabela `preferencias` do banco e mantidos entre sessões.

---

## 🐛 Bug Fixes da Sprint 1 (Revisão)

1. **Crash Android (`no such table: hino`)** — `pyproject.toml` + pasta `assets/` + `connection.py`
2. **Android PermissionError (`/data/.local`)** — Resolução de caminhos com `FLET_APP_STORAGE_DATA` e fallback em `tempfile.gettempdir()`
3. **SnackBar Leak** — Singleton `_show_snackbar()` na `HinoView`
4. **Query de Recentes Bugada** — Subquery `MAX(data_acesso)` com desempate por `MAX(id)`
5. **Scoring do Agente** — Scoring com hinos completos + JOIN com tabela `tema`

---

## 📋 Resumo de Arquivos Alterados

| Arquivo | Tipo | Descrição |
|---|---|---|
| `pyproject.toml` | Config | Versão 0.2 + assets + icon.ico |
| `icon.ico` | Asset | Ícone oficial do aplicativo |
| `assets/hinario_normalizado.db` | Asset | Banco SQLite de 601 hinos |
| `setup_assets.sh` | Script | Setup automatizado da pasta assets/ |
| `main.py` | Core | Roteamento com query string `?q=`, window icon, LRU |
| `src/database/connection.py` | Database | Índices SQL, tabela `hino_fts`, `preferencias`, limpeza de histórico |
| `src/repositories/hino_repository.py` | Repository | Busca FTS5, `get_categorias()`, `get_temas()`, busca por categoria/tema |
| `src/views/hino_view.py` | View | BottomAppBar com labels, chips no modal info, persistência de fontes |
| `src/views/home_view.py` | View | Loading state, empty states, aba Explorar, busca por query string |
| `src/views/agente_view.py` | View | Layout 100% responsivo para landscape, chips, slider |
| `tests/test_hino_repository.py` | Testes | Cobertura para categorias, temas e buscas por tag |

---

## 🔮 Próximas Sprints — Backlog Futuro (Fase 3)

### Sprint 3 — Mídia & Cultos
- [ ] **Player de vídeo embutido (YouTube)**
- [ ] **Modo execução de culto** (tela cheia para uso durante o culto)
- [ ] **CRUD de cultos salvos** (excluir, renomear, reordenar hinos)
- [ ] **Gerenciador de downloads offline**

### Longo Prazo
- [ ] **Integração da Bíblia Sagrada completa no banco de dados**
- [ ] **Suporte a múltiplas versões bíblicas**
- [ ] **Kit completo: Hinário Novo + Antigo + Bíblia**
