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

## Documentación

Lee `CLAUDE.md` para entender el contexto del proyecto, terminología (Edge A/B, CLV, sharp/soft), principios de decisión y convenciones técnicas.
