# clv-poc

Sistema de detección de edges en apuestas deportivas basado en **Closing Line Value (CLV)**: explotar el retraso de casas "soft" (Bet365, Bwin, Winamax...) respecto al precio de cierre de Pinnacle (casa "sharp" de referencia).

## Arranque

```bash
# Instalar dependencias
uv sync

# Crear .env con tu clave de The Odds API
cp .env.example .env
# Edita .env y añade tu ODDS_API_KEY

# Ejecutar tests
uv run pytest

# Ejecutar linter
uv run ruff check .
```

## Arquitectura

El repo está organizado por responsabilidad:

- `client/` — clientes HTTP para APIs externas (The Odds API, etc.)
- `storage/` — persistencia (SQLite/DuckDB)
- `scheduler/` — polling y scheduling (cron, APScheduler)
- `analysis/` — cálculo de CLV y reportes

## Captura de cuotas

`config.yaml` define los targets (liga + sharp book + soft books) a capturar. Añadir una liga futura es solo editar el YAML, sin tocar código.

```bash
# Captura manual de un target concreto (para debug/verificación real)
uv run python -m scheduler.capture --target world_cup_2026

# Captura de todos los targets activos (lo que ejecuta cron)
uv run python -m scheduler.capture
```

Cada ejecución comprueba la cuota real restante (llamada gratis) antes de gastar crédito, y aborta un target si el margen mínimo configurado (`min_remaining_credits`) no se respeta. La confirmación explícita que exige el "Guardrail de coste" de `CLAUDE.md` para este job recurrente se da una vez, al revisar y aprobar `config.yaml` (qué targets, qué bookmakers, coste por ejecución) — no en cada disparo de cron.

### Programar la captura (cron)

No instalado automáticamente. Línea sugerida (cada 3h):

```
0 */3 * * * cd /home/edu/code/clv-poc && /home/edu/.local/bin/uv run python -m scheduler.capture >> /home/edu/code/clv-poc/data/capture.log 2>&1
```

Confirma la ruta exacta de `uv` con `which uv` antes de instalarla — el `PATH` mínimo de cron es una fuente común de fallos silenciosos.

## Documentación

Lee `CLAUDE.md` para entender el contexto del proyecto, terminología (Edge A/B, CLV, sharp/soft), principios de decisión y convenciones técnicas.
