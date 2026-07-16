# clv-poc

Sistema de detección de edges en apuestas deportivas basado en **Closing Line Value (CLV)**. La premisa: casas "sharp" como Pinnacle fijan precios muy cercanos a la probabilidad real porque absorben volumen informado. Casas "soft" (Williamhill, Betvictor, Winamax...) tardan más en reaccionar. Ese retraso es la ineficiencia que se mide.

> El proyecto está en fase POC (Edge A): capturar datos reales y verificar si existe CLV positivo consistente. No se ejecutan apuestas reales.

## ⚠️ Disclaimer

**Este proyecto es un ejercicio de investigación personal. No está diseñado para generar beneficio económico ni debe usarse para apostar dinero real.**

- El resultado más probable de este POC es **no encontrar ningún edge explotable**. Detectar CLV positivo consistente en mercados líquidos es extremadamente difícil; la hipótesis puede simplemente ser falsa o insuficiente a esta escala.
- Incluso si el análisis mostrase CLV positivo, eso **no implica rentabilidad real**: los datos de The Odds API tienen latencia, las cuotas que ve un apostador real incluyen limitaciones de cuenta, y la varianza a corto plazo es enorme.
- **No se debe usar este código para tomar decisiones de apuesta con dinero real.** El autor no asume ninguna responsabilidad por pérdidas derivadas de un uso distinto al de investigación.
- Las apuestas deportivas conllevan riesgo de pérdida. Si tienes o crees tener un problema con el juego, busca ayuda en [jugarbien.es](https://www.jugarbien.es) (España) o el servicio equivalente de tu país.

## Arranque rápido

```bash
# Instalar dependencias
uv sync

# Configurar clave de API
cp .env.example .env
# Edita .env y añade ODDS_API_KEY (the-odds-api.com)

# Ejecutar tests
uv run pytest

# Linter
uv run ruff check .
```

## Arquitectura

```
client/      → cliente HTTP para The Odds API (dry_run=True por defecto)
storage/     → DuckDB local: tabla snapshots (append-only) + mart clv_snapshots
scheduler/   → captura de cuotas: capture.py (one-shot/cron) + daemon.py (APScheduler)
analysis/    → cálculo de CLV y devig sobre cierres de Pinnacle
dashboard/   → dashboard Streamlit local para visualizar resultados
scripts/     → utilidades de verificación y diagnóstico
config.yaml  → targets activos (liga + sharp + soft books), sin tocar código al añadir uno
```

Almacenamiento local en DuckDB (`data/odds.duckdb`). Sin bases de datos gestionadas ni infraestructura cloud en esta fase.

## Targets activos

Definidos en `config.yaml`. Añadir una liga nueva es solo editar el YAML:

| Target | Sport key | Sharp | Soft books |
|---|---|---|---|
| `world_cup_2026` | `soccer_fifa_world_cup` | Pinnacle | williamhill, betvictor, winamax_fr, marathonbet |
| `mls_2026` | `soccer_usa_mls` | Pinnacle | williamhill, betvictor, winamax_fr, marathonbet |

Cobertura confirmada empíricamente el 2026-07-06 (`scripts/check_soft_book_coverage.py`): los 4 soft books tenían precio en los 6 eventos del Mundial consultados.

## Modos de captura

### Daemon (recomendado)

Proceso de larga duración que descubre eventos cada 12h, programa capturas de trayectoria (cada 3h por target) y una **ráfaga de cierre** a 6 y 2 minutos antes de cada inicio. Resiliente a reinicios: reconstruye la agenda al arrancar.

```bash
uv run python -m scheduler.daemon
```

Logs rotativos en `logs/daemon.log` (10 MB × 5 ficheros).

### Captura manual / cron

One-shot: hace su trabajo y termina. Útil para debug o para ejecutar vía cron.

```bash
# Todos los targets activos
uv run python -m scheduler.capture

# Un target concreto (debug)
uv run python -m scheduler.capture --target world_cup_2026
```

Línea cron sugerida (cada 3h):

```
0 */3 * * * cd /home/edu/code/clv-poc && /home/edu/.local/bin/uv run python -m scheduler.capture >> data/capture.log 2>&1
```

Confirma la ruta de `uv` con `which uv` antes de instalarla — el PATH mínimo de cron es fuente común de fallos silenciosos.

## Guardrail de coste

Antes de gastar crédito real, `capture.py` llama al endpoint gratuito `/sports` para leer la cuota restante y aborta si el margen post-llamada caería por debajo de `min_remaining_credits` (config.yaml). El cierre **nunca** se sacrifica por el guardrail — si hay que recortar, se recorta trayectoria primero.

El cliente en `client/odds_api.py` tiene `dry_run=True` por defecto en cualquier método que consuma cuota. Solo gasta crédito si se pasa `dry_run=False` explícitamente.

## Análisis CLV

Reconstruye la tabla `clv_snapshots` (full refresh) calculando el CLV de cada snapshot soft contra el cierre fair de Pinnacle (con devig).

```bash
# Todos los targets activos
uv run python -m analysis.report

# Un target (debug)
uv run python -m analysis.report --target world_cup_2026
```

Solo se considera benchmark válido un cierre capturado ≤ 15 minutos antes del inicio. Los snapshots sin cierre válido quedan en `clv_snapshots` con `clv = NULL` e `is_valid_closing_benchmark = False`.

## Dashboard

Dashboard Streamlit local que lee `data/odds.duckdb` en modo read-only:

```bash
uv run streamlit run dashboard/app.py
```

Muestra:
- **CLV medio por soft book** (criterio go/no-go del POC)
- **Trayectoria por evento** (evolución de cuotas según se acerca el cierre)
- **Salud de captura** (capturas por día y sport_key)
- **Tabla cruda** `clv_snapshots` con filtros

## Scripts de diagnóstico

```bash
# Verificar créditos restantes (coste 0)
uv run python scripts/check_odds_api_credits.py

# Verificar cobertura de soft books en un target
uv run python scripts/check_soft_book_coverage.py

# Verificación real de Pinnacle en tier gratuito (gasta 1 crédito, pide confirmación)
uv run python scripts/verify_pinnacle.py
```

## Documentación

Lee `CLAUDE.md` para el contexto completo del proyecto: terminología (Edge A/B, CLV, sharp/soft), principios de decisión, convenciones técnicas y guardrails.
