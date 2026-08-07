# Changelog — Sprint: Bug Fixes + Quick Wins

> Documento gerado automaticamente com todas as alterações desta sprint e itens pendentes para futuras implementações.

---

## 📅 Data: 2026-08-07

## 🎯 Objetivo da Sprint
Correção de bugs críticos (incluindo crash no Android) e implementação de quick wins de performance, UX e funcionalidade identificados na análise do código.

---

## 🐛 Bug Fixes Implementados

### 1. Crash Android: `no such table: hino` (CRÍTICO)

**Problema:** O `flet build apk` não empacotava o banco de dados `hinario_normalizado.db`. O app crashava imediatamente no Android.

**Causa raiz:** Ausência de `pyproject.toml` com configuração de assets e de pasta `assets/`.

**Correção:**
- Criado `pyproject.toml` com `[tool.flet] app.assets_dir = "assets"`
- Criada pasta `assets/` com cópia do banco de dados
- Atualizado `connection.py` para buscar o banco na pasta `assets/` e suportar `FLET_APP_STORAGE_DATA`

**Arquivos alterados:**
- `pyproject.toml` (NOVO)
- `assets/hinario_normalizado.db` (NOVO)
- `src/database/connection.py`

---

### 2. SnackBar Leak (Vazamento de Memória)

**Problema:** Cada ação (favoritar, download, erro) criava um novo `ft.SnackBar` e appendava ao `page.overlay` sem remover os anteriores, causando acúmulo de elementos no DOM e possíveis bugs visuais.

**Correção:** Implementado `_show_snackbar(page, msg)` que reutiliza um único SnackBar singleton, apenas atualizando o texto.

**Arquivos alterados:**
- `src/views/hino_view.py`

---

### 3. Query de Recentes Bugada

**Problema:** `SELECT DISTINCT` não garantia retornar o acesso mais recente de cada hino. Em casos com múltiplos acessos ao mesmo hino, o resultado podia ser incorreto.

**Correção:** Subquery com `MAX(data_acesso)` agrupado por `hino_id`:
```sql
SELECT h.id, h.numero, h.titulo
FROM hino h
INNER JOIN (
    SELECT hino_id, MAX(data_acesso) AS ultimo_acesso
    FROM historico
    GROUP BY hino_id
) latest ON h.id = latest.hino_id
ORDER BY latest.ultimo_acesso DESC
LIMIT ?
```

**Arquivos alterados:**
- `src/repositories/historico_repository.py`

---

### 4. Scoring do Agente Não Funcionava

**Problema:** Candidatos vindos de `search()` só tinham `titulo` preenchido (sem `categoria`/`subcategoria`/`texto_base`). O scoring por esses campos nunca pontuava, resultando em sugestões genéricas.

**Correção:** O agente agora carrega hinos completos via `get_by_id()` com cache in-memory. Além disso, usa JOINs com a tabela `tema` (2112+ relações no banco) para scoring.

**Arquivos alterados:**
- `src/services/agente_service.py`

---

### 5. Bug no Teste: `get_all_hinos()` inexistente

**Problema:** O teste `test_real_db_connection_and_hino_table` chamava `get_all_hinos()` que não existe no `HinoRepository`.

**Correção:** Renomeado para `get_all()`.

**Arquivos alterados:**
- `tests/test_database_connection.py`

---

## ⚡ Melhorias de Performance

### 1. Remoção de `letra` da Listagem

A Home só exibe número e título, mas carregava a letra completa (~643 chars × 601 hinos ≈ 386 KB por carregamento). Removida a coluna `letra` das queries `get_all()` e `search()`.

**Arquivos alterados:**
- `src/repositories/hino_repository.py`

---

### 2. Invalidação do Cache da Home

A Home era cacheada para sempre. Ao favoritar e voltar, a aba "Favoritos" não refletia a mudança. Agora o cache é invalidado ao retornar de `/hino/*`.

**Arquivos alterados:**
- `main.py`

---

### 3. LRU Cache para Views de Hinos

Cada `/hino/{id}` visitado ficava no cache para sempre. Implementado LRU com máximo de 10 views via `OrderedDict`.

**Arquivos alterados:**
- `main.py`

---

### 4. `asyncio.gather` no HinoView

As 4 queries ao abrir um hino (get_by_id, add_acesso, get_metadados_relacionados, is_favorito) agora rodam em paralelo com `asyncio.gather`, reduzindo a latência de abertura.

**Arquivos alterados:**
- `src/views/hino_view.py`

---

## 🎨 Melhorias de UX/Funcionalidade

### 1. Modo Claro/Escuro Automático

`page.theme_mode = ft.ThemeMode.SYSTEM` detecta automaticamente o tema do sistema operacional (dia/noite). Removido `ft.ThemeMode.DARK` hardcoded das views.

**Arquivos alterados:**
- `main.py`
- `src/views/home_view.py` (removido `page.theme_mode = ft.ThemeMode.DARK`)

---

### 2. Navegação Anterior/Próximo

Adicionados botões `←` (anterior) e `→` (próximo) na AppBar da `HinoView`. A navegação usa a lista ordenada de IDs dos hinos carregada pelo `main.py`.

**Arquivos alterados:**
- `src/views/hino_view.py` (novo parâmetro `hino_ids_list`, método `_build_nav_buttons`)
- `main.py` (calcula e passa `hino_ids_ordered`)

---

### 3. Voltar com Stack de Views

O botão voltar de `HinoView` e `AgenteView` agora usa `page.views.pop()` em vez de `page.go("/")`, preservando o contexto de navegação. Se o usuário veio do Agente, volta para o Agente.

**Arquivos alterados:**
- `src/views/hino_view.py`
- `src/views/agente_view.py`

---

### 4. Subtitle Redundante Removido

O `subtitle=ft.Text(f"Hino {hino.numero}")` duplicava a informação do `leading`. Removido para uma interface mais limpa.

**Arquivos alterados:**
- `src/views/home_view.py`

---

### 5. Chips de Exemplo no Agente

Adicionados chips clicáveis com temas de exemplo: "Gratidão", "Batismo", "Páscoa", "Fé", "Família", "Esperança", "Louvor", "Natal". Ao clicar, o tema preenche o campo de texto.

**Arquivos alterados:**
- `src/views/agente_view.py`

---

### 6. Slider de Quantidade de Hinos no Agente

Adicionado slider (4–10 hinos) para que o usuário escolha quantos hinos quer na sugestão de culto. Os blocos litúrgicos foram expandidos para até 10 momentos.

**Arquivos alterados:**
- `src/views/agente_view.py`
- `src/services/agente_service.py` (novo parâmetro `num_hinos`)

---

### 7. Scoring Melhorado com Temas

O agente agora pontua candidatos usando:
- +5 para match no título
- +4 para match nos temas do banco (tabela `tema` → `hino_tema`)
- +3 para match em categoria/subcategoria
- +2 para match no texto base bíblico

**Arquivos alterados:**
- `src/services/agente_service.py`

---

## 🧪 Alterações em Testes

- `conftest.py`: Adicionadas tabelas `tema`, `hino_tema`, `texto_biblico`, `hino_texto` com dados sintéticos
- `test_database_connection.py`: Corrigida referência a método inexistente

---

## 📋 Resumo de Todos os Arquivos Alterados

| Arquivo | Tipo | Status |
|---|---|---|
| `pyproject.toml` | Config | ✅ NOVO |
| `assets/hinario_normalizado.db` | Asset | ⚠️ Copiar manualmente |
| `main.py` | Core | ✅ Modificado |
| `src/database/connection.py` | Database | ✅ Modificado |
| `src/repositories/hino_repository.py` | Repository | ✅ Modificado |
| `src/repositories/historico_repository.py` | Repository | ✅ Modificado |
| `src/services/agente_service.py` | Service | ✅ Modificado |
| `src/views/hino_view.py` | View | ✅ Modificado |
| `src/views/home_view.py` | View | ✅ Modificado |
| `src/views/agente_view.py` | View | ✅ Modificado |
| `tests/conftest.py` | Test | ✅ Modificado |
| `tests/test_database_connection.py` | Test | ✅ Modificado |

---

## 🔮 Próximas Sprints — Backlog de Funcionalidades

### Sprint 2 — Valor Litúrgico (estimativa: 1 semana)
- [ ] **Player de vídeo embutido** — `ft.Video` ou WebView para reprodução de hinos do YouTube direto no app
- [ ] **FTS5 para busca na letra** — Busca full-text em letra, categoria, tema e texto bíblico
- [ ] **Modo execução de culto** — Tela cheia com hino atual, próximo, timer e controle de fluxo
- [ ] **Persistir preferências de fonte** — Tamanho, família e tema salvos entre sessões
- [ ] **Aba "Explorar"** — Navegação por categoria/tema com chips clicáveis
- [ ] **CRUD completo de cultos** — Excluir, renomear, reordenar hinos, duplicar

### Sprint 3 — Polimento (estimativa: 2+ semanas)
- [ ] **Tema claro com toggle manual** — 3 estados: Claro / Escuro / Automático
- [ ] **Embeddings locais (SQLite-VSS)** — Busca semântica real para o agente
- [ ] **Gerenciador de downloads** — Lista, excluir, espaço usado
- [ ] **Exportar culto** — PDF/texto/WhatsApp
- [ ] **Build Android com fontes bundled** — OpenDyslexic offline
- [ ] **Atalhos de teclado (desktop)** — Ctrl+F, ←/→, Space para play
- [ ] **Animações de transição** — Transições suaves entre telas
- [ ] **Empty states ilustrados** — Favoritos/recentes vazios com ilustração
- [ ] **Índices no banco** — `historico(hino_id, data_acesso)`, `favorito(data_favoritado)`, `hino(numero)`

### Roadmap de Longo Prazo
- [ ] **Melhorar formatação dos hinos** — Separar em estrofes/coro em vez de texto corrido
- [ ] **Adicionar a Bíblia completa como DB** — Incluir passagens na parte de informações dos hinos
- [ ] **Melhorar correlação hino-bíblia** — Relacionar com textos além do texto base
- [ ] **Múltiplas versões da Bíblia** — ARA, NVI, ACF, etc.
- [ ] **Mudar escopo para kit completo** — Hinário Novo + Antigo + Bíblia em um único app
