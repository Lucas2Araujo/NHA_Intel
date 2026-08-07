# 📊 Análise de Progresso: updateapp.md vs Estado Atual

Cruzamento detalhado entre todas as sugestões do diagnóstico original e o que já foi implementado na Sprint 1 (v0.2).

---

## 🟢 Performance — O que JÁ FOI implementado

| # | Item do updateapp.md | Status | Arquivo |
|---|---|---|---|
| 1 | Home carregava `letra` sem necessidade | ✅ Feito | `hino_repository.py` — queries agora selecionam só `id, numero, titulo` |
| 2 | View cache da Home ficava obsoleta | ✅ Feito | `main.py` — invalida cache ao voltar de `/hino/*` |
| 3 | Cache de HinoViews crescia sem limite | ✅ Feito | `main.py` — LRU com `OrderedDict`, máx 10 views |
| 4 | HinoView fazia 4 queries sequenciais | ✅ Feito | `hino_view.py` — `asyncio.gather` para queries paralelas |
| 6 | Bug no histórico — `DISTINCT` errado | ✅ Feito | `historico_repository.py` — subquery `MAX(data_acesso)` + desempate `MAX(id)` |

---

## 🔴 Performance — O que FALTA implementar

| # | Item do updateapp.md | Status | Impacto | Esforço |
|---|---|---|---|---|
| 5 | Agente faz N queries sequenciais por keyword | ⚠️ Parcial | Médio | Médio |
| 7 | **Sem índices no banco** | ❌ Não feito | Médio (cresce com o tempo) | Baixo |
| 8 | **Ordenação quebra em hinos `587_A`/`587_B`** | ❌ Não feito | Baixo | Baixo |
| 9 | **Rebuild de 601 tiles a cada keystroke** | ❌ Não feito | Médio | Médio |

> **Nota sobre item 5**: O agente agora carrega hinos completos com cache in-memory e usa temas do banco, mas as queries por keyword ainda são sequenciais (`for kw in palavras_relevantes: search(kw)`). A solução ideal seria uma query SQL única com `OR`/`UNION` ou usar o FTS5.

---

## 🟢 Funcionalidade — O que JÁ FOI implementado

| # | Item do updateapp.md | Status | Arquivo |
|---|---|---|---|
| 2a | Agente: scoring usando JOIN com temas | ✅ Feito | `agente_service.py` — scoring com temas, categoria, subcategoria, texto_base |
| 2b | Agente: retornar 8-10 hinos | ✅ Feito | `agente_service.py` + `agente_view.py` — slider 4-10 hinos |
| 4 | Navegação anterior/próximo | ✅ Feito | `hino_view.py` — botões ←/→ no AppBar |

---

## 🔴 Funcionalidade — O que FALTA implementar

| # | Item do updateapp.md | Status | Impacto | Esforço |
|---|---|---|---|---|
| 1 | **Busca na letra/temas/categorias (FTS5)** | ❌ Não feito | Muito alto | Médio |
| 2c | Agente: trocar hino por bloco individual | ❌ Não feito | Alto | Médio |
| 3 | **Reprodutor de mídia incompleto** | ❌ Não feito | Alto | Médio-Alto |
| | - Pause vs Stop (hoje Stop mata o processo) | ❌ | | |
| | - Barra de progresso decorativa (indeterminada) | ❌ | | |
| | - Player de vídeo embutido | ❌ | | |
| | - play_audio com URL extraída por get_info() | ❌ | | |
| | - Indicador de progresso no download | ❌ | | |
| | - Gerenciador de downloads | ❌ | | |
| 5 | **CRUD completo de cultos salvos** | ❌ Não feito | Médio | Médio |
| | - Excluir culto | ❌ | | |
| | - Renomear culto | ❌ | | |
| | - Reordenar hinos no culto | ❌ | | |
| | - Duplicar culto | ❌ | | |
| | - Exportar (PDF/texto/WhatsApp) | ❌ | | |
| 6 | **Preferências não persistem** | ❌ Não feito | Médio | Baixo |
| 7 | **Exploração por categoria/tema** | ❌ Não feito | Alto | Médio |
| 8 | **Modo offline parcial** (OpenDyslexic via CDN) | ❌ Não feito | Baixo | Baixo |

---

## 🟢 UX/UI — O que JÁ FOI implementado

| # | Item do updateapp.md | Status | Arquivo |
|---|---|---|---|
| 1 | Só dark mode → tema automático | ✅ Feito | `main.py` — `ft.ThemeMode.SYSTEM` |
| 3 | SnackBars acumulam no overlay | ✅ Feito | `hino_view.py` — SnackBar singleton `_show_snackbar()` |
| 4 | Voltar sempre ia para `/` | ✅ Feito | `hino_view.py` + `agente_view.py` — `page.views.pop()` com stack |
| 7 | Agente sem orientação | ✅ Feito | `agente_view.py` — chips de exemplo clicáveis |
| 10a | Subtitle redundante `"Hino {numero}"` | ✅ Feito | `home_view.py` — removido |

---

## 🔴 UX/UI — O que FALTA implementar

| # | Item do updateapp.md | Status | Impacto | Esforço |
|---|---|---|---|---|
| 2 | **Feedback visual insuficiente** | ❌ Não feito | Médio | Baixo |
| | - Home sem loading no primeiro carregamento | ❌ | | |
| | - Download sem barra de progresso real | ❌ | | |
| | - Indicador "último hino acessado" na Home | ❌ | | |
| 5 | **BottomAppBar sem rótulos** (trial-and-error) | ❌ Não feito | Médio | Baixo |
| 6 | **Temas/textos bíblicos como texto corrido** (deveria ser chips clicáveis) | ❌ Não feito | Alto | Médio |
| 8 | **Lista flat de 601 itens** (sem agrupamento visual) | ❌ Não feito | Médio | Médio |
| 9 | **Acessibilidade incompleta** | ❌ Parcial | Médio | Médio |
| | - OpenDyslexic só Regular (falta Bold/Italic) | ❌ | | |
| | - Sem alto contraste / tema sepia | ❌ | | |
| | - Sem preferência global de fonte persistida | ❌ | | |
| | - Desktop: sem atalhos de teclado | ❌ | | |
| 10b | Sem animação de transição entre telas | ❌ Não feito | Baixo | Baixo |
| 10c | Sem empty states ilustrados | ❌ Não feito | Baixo | Baixo |

---

## 🔴 Features pedidas pelo usuário (updateapp.md linhas 658-672) — Status

| Feature | Status | Observação |
|---|---|---|
| Modo claro automático (ciclo dia/noite) | ✅ Feito | `ft.ThemeMode.SYSTEM` |
| Player de vídeo embutido (YouTube) | ❌ Não feito | Adiado para Sprint 2 |
| Agente: seleção de quantos hinos | ✅ Feito | Slider 4-10 no `agente_view.py` |
| Agente: opções de temas | ✅ Feito | Chips clicáveis + scoring com tabela `tema` |
| Agente: busca só por texto bíblico | ❌ Não feito | Precisa de filtro dedicado |
| Melhorar formatação dos hinos (estrofes) | ❌ Não feito | Mudança no banco de dados |
| Adicionar Bíblia como DB | ❌ Não feito | Feature de longo prazo |
| Melhorar correlação hino-bíblia | ❌ Não feito | Feature de longo prazo |
| Escopo expandido (Hinário + Bíblia) | ❌ Não feito | Feature de longo prazo |

---

## 📈 Resumo Quantitativo

| Categoria | Total de itens | ✅ Feitos | ❌ Pendentes | % Completo |
|---|---|---|---|---|
| **Performance** | 9 | 5 | 4 | 56% |
| **Funcionalidade** | 12 | 3 | 9 | 25% |
| **UX/UI** | 14 | 5 | 9 | 36% |
| **Features do Usuário** | 9 | 3 | 6 | 33% |
| **TOTAL** | **44** | **16** | **28** | **36%** |

---

## 🧠 Minhas Sugestões para a Próxima Sprint (Sprint 2)

Baseado no que analisei, organizei as sugestões em 3 tiers por **relação impacto/esforço**:

### 🏆 Tier 1 — Alto Impacto, Esforço Baixo (1-2 dias)

Essas mudanças são rápidas e fazem grande diferença na percepção de qualidade do app:

| # | Sugestão | Justificativa |
|---|---|---|
| 1 | **Índices SQL no banco** | 4 `CREATE INDEX` no startup. Previne degradação futura à medida que histórico e favoritos crescem. Demora 5 minutos. |
| 2 | **Loading state na Home** | Adicionar `ProgressRing` enquanto carrega os 601 hinos no primeiro build. Evita tela "seca". |
| 3 | **Empty states** nos Favoritos/Recentes vazios | Texto amigável + ícone ao invés de lista vazia. Ex: "Nenhum hino favorito ainda. Toque no ❤️ para salvar seus hinos favoritos!" |
| 4 | **Labels na BottomAppBar do HinoView** | Adicionar texto descritivo ("Fonte", "Mídia", "Download") abaixo dos ícones — especialmente em contexto de igreja com usuários variados. |
| 5 | **Persistir preferências de fonte** | Salvar `font_size` e `font_family` em JSON local ou tabela `preferencias`. Recarregar no startup. |
| 6 | **Limpeza automática de histórico** | `DELETE FROM historico WHERE data_acesso < datetime('now', '-90 days')` no startup. Evita tabela crescer para sempre. |

### ⚡ Tier 2 — Alto Impacto, Esforço Médio (3-5 dias)

Essas são funcionalidades novas que mudam a experiência do app significativamente:

| # | Sugestão | Justificativa |
|---|---|---|
| 7 | **FTS5 para busca full-text** | Permite buscar "amor", "salvação" ou "João 3:16" direto na letra/temas. Transforma a busca de "busca por número e título" para "busca real de conteúdo". É a feature mais pedida em apps de hinário. |
| 8 | **Aba "Explorar" por categorias/temas** | O banco tem categorias e 2112 relações com temas. Uma aba com chips clicáveis ("Adoração", "Louvor", "Batismo"…) é navegação natural para quem não sabe o número. |
| 9 | **Temas e textos bíblicos como chips clicáveis** no modal de info do hino | Em vez de texto corrido, cada tema/texto vira um chip que ao clicar filtra a busca. Conecta o app todo. |
| 10 | **CRUD de cultos: excluir + renomear** | Só os dois mais essenciais. Duplicar e exportar podem ficar para depois. |
| 11 | **Agente: trocar hino individual por bloco** | Botão "🔄" ao lado de cada hino sugerido que regenera só aquele slot. Muito útil na prática litúrgica. |

### 🔬 Tier 3 — Alto Impacto, Esforço Alto (1+ semana)

Para sprints futuras:

| # | Sugestão | Justificativa |
|---|---|---|
| 12 | **Player de vídeo embutido** | Usar `ft.Video` do Flet ou WebView para reprodução direta do YouTube. |
| 13 | **Modo execução de culto** | Tela cheia: hino atual com letra, próximo, timer, controle de fluxo. Para usar durante o culto real. |
| 14 | **Barra de progresso real no player de áudio** | Integrar com a duração extraída por `get_info()` e atualizar a ProgressBar em tempo real. |
| 15 | **Exportar culto** (PDF/texto/WhatsApp) | Compartilhar a lista de hinos com a equipe de louvor. |
| 16 | **Formatação dos hinos em estrofes** | Separar letra em blocos (estrofe/coro) em vez de texto corrido — requer alteração no banco. |

---

## 🎯 Proposta: Sprint 2 — "Busca Real + Polimento"

Se você concordar, sugiro esta sprint focada em **Tier 1 completo + itens 7, 8, 9 do Tier 2**:

### Escopo proposto

1. ✅ Índices SQL (startup)
2. ✅ Loading state na Home
3. ✅ Empty states (Favoritos/Recentes)
4. ✅ Labels na BottomAppBar
5. ✅ Persistir preferências de fonte
6. ✅ Limpeza de histórico (90 dias)
7. ⚡ **FTS5 busca full-text** (letra, temas, textos bíblicos)
8. ⚡ **Aba "Explorar"** por categorias/temas
9. ⚡ **Chips clicáveis** no modal de info do hino

### Estimativa: 3-5 dias de desenvolvimento

> [!IMPORTANT]
> **Decisão necessária**: Você quer seguir com essa proposta de Sprint 2, ou prefere priorizar algo diferente? Por exemplo, se o CRUD de cultos ou o player de vídeo for mais urgente para o seu uso, posso reorganizar.
