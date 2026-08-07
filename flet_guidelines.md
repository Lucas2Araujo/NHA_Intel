# Diretrizes de Engenharia e Sintaxe do Flet (Flet 0.85+ Assíncrono)

Este documento estabelece as convenções de código, padrões de arquitetura e sintaxe assíncrona do Flet para o projeto **Hinário Inteligente**.

---

## 1. Ponto de Entrada Assíncrono e Roteamento
- **Utilizar `async def main(page: ft.Page)`** com `ft.run(main)`.
- Gerenciar rotas assincronamente através de `async def route_change(e=None)` e `async def view_pop(e)`.
- **View Caching:** Armazenar instâncias de `ft.View` construídas em um dicionário `view_cache: Dict[str, ft.View]` para reutilização rápida ao navegar entre telas sem recriar o DOM.

---

## 2. Acesso a Dados Assíncrono (`aiosqlite`)
- Acesso a dados obrigatoriamente não-bloqueante utilizando `aiosqlite`.
- Gerenciador de contexto `async with` para conexões e cursores.
- Consultas SQL estritamente parametrizadas (`?`) em métodos `async def`.

---

## 3. Imutabilidade do Domínio (DTO)
- Todas as entidades de transferência de dados devem ser DTOs imutáveis com **`@dataclass(frozen=True)`**.
- Garante segurança contra efeitos colaterais e otimiza a alocação de memória.

---

## 4. Debounce em Operações de Interface
- Operações de pesquisa rápida com I/O assíncrono devem utilizar **debounce de 300ms** (`await asyncio.sleep(0.3)`).
- Tarefas de busca anteriores devem ser canceladas (`task.cancel()`) se o usuário continuar digitando.

---

## 5. Virtualização de Listas
- **Obrigatoriedade do `ft.ListView` para listas extensas:**
  Sempre utilizar `ft.ListView` para renderizar coleções de dados (como os 601 hinos). O `ft.ListView` possui virtualização nativa no Flutter engine.

---

## 6. Componentes e Padrões Flet
- Alinhamento: `ft.Alignment.CENTER`, `ft.Alignment.TOP_CENTER` (PascalCase).
- Preenchimento: `ft.Padding.all()`, `ft.Padding.symmetric()` (PascalCase).
- Cores: `ft.Colors` (PascalCase).
- Tipografia: `ft.FontWeight` (PascalCase).
