# Contexto de proyecto y convenciones de desarrollo

Este documento es tu contexto permanente como developer en este proyecto. Léelo antes de tocar cualquier código y vuelve a él si dudas cómo proceder.

## Qué es este proyecto

Sistema de detección de edges en apuestas deportivas basado en **Closing Line Value (CLV)**. La idea central: casas "sharp" (principalmente Pinnacle) fijan precios muy cercanos a la probabilidad real porque absorben mucho volumen informado. Casas "soft" (Bet365, Bwin, Winamax...) tardan más en reaccionar a esa información. Ese retraso es la ineficiencia que se explota.

### Terminología que se usa sin explicar cada vez

- **Edge A**: explotar el retraso de las soft books respecto a Pinnacle como referencia. Es el único edge que se está construyendo ahora.
- **Edge B**: construir un modelo propio de probabilidad para batir a Pinnacle directamente. Está **descartado para esta fase** — es extremadamente difícil en mercados líquidos y no se toca hasta que Edge A esté validado.
- **CLV**: la métrica de éxito. No es profit/loss (ruidoso a corto plazo), es si el precio capturado bate consistentemente al precio de cierre de Pinnacle.
- **Sharp / soft**: clasificación de bookmakers por eficiencia de precio, no por tamaño ni reputación.

## Cómo se toman las decisiones en este proyecto

1. **Verificación real por encima de memoria o documentación de marketing.** Si hay que confirmar cómo se comporta una API, un endpoint, un límite de cuota o un dato de mercado, se hace una llamada real y se reporta el resultado exacto (incluyendo error o vacío), no lo que dice la web de producto o lo que "se sabe" de otros proyectos. Si no se puede verificar, se dice explícitamente que es una suposición pendiente de confirmar, nunca se presenta como hecho.
2. **Roadmap por etapas, sin adelantarse.** Primero se valida que existe la ineficiencia (Edge A) con el mínimo pipeline posible. Solo después de tener señal real se añade complejidad (scraping propio, self-healing con LLM, modelos de probabilidad, infraestructura de producción). No se construye nada de la fase 2 "por si acaso" mientras la fase 1 no está validada.
3. **Conciencia de coste explícita.** Antes de implementar algo que consuma cuota de API, proxies, o cómputo, se calcula cuánto cuesta a la escala real del POC y se dice el número. No se optimiza para escala que aún no existe.
4. **No avanzar sin confirmar el paso anterior.** Si una tarea depende de un supuesto (p. ej. "Pinnacle está en el tier gratuito"), esa dependencia se verifica primero y se para si falla, en vez de seguir construyendo encima de un supuesto no confirmado.

## Convenciones técnicas del proyecto

- **Entorno**: máquina local (Fedora), sin infraestructura cloud en esta fase salvo que se decida explícitamente lo contrario.
- **Lenguaje por defecto**: Python, salvo que la tarea concreta pida otra cosa.
- **Almacenamiento**: SQLite o DuckDB local. Nada de bases de datos gestionadas en el POC.
- **Scheduling**: cron o APScheduler. Nada de orquestadores pesados (Airflow, etc.) a esta escala.
- **LLM como herramienta de desarrollo**: si en algún momento se usa un LLM dentro del propio sistema (no como developer, sino como componente), el único uso válido hoy es *self-healing de selectores* cuando se rompe un scraper — nunca parseo de cada página ni generación de señales de trading. Preferentemente modelo local (Ollama/vLLM) para coste marginal ~$0.
- **Estructura de repo**: carpetas separadas por responsabilidad (ej. `/client` para llamadas a APIs externas, `/storage` para persistencia, `/scheduler` para el polling, `/analysis` para cálculo de CLV y reportes). Evitar scripts monolíticos.
- **Logging**: cualquier componente que consuma cuota o dinero real (llamadas a API, proxies) debe loggear el coste real de cada operación, no solo el resultado. Esto es así porque el coste ya ha causado sorpresas antes en este proyecto.
- **Testing**: antes de dar por válida una pieza (cliente API, cálculo de CLV, etc.), demostrar con un output real y pequeño que hace lo esperado, no solo que el código "compila" o no lanza excepciones.

## Guardrail de coste

Ninguna llamada a un endpoint que consuma cuota (`/v4/sports/{sport}/odds`, `/v4/historical/...`) se ejecuta — ni se sugiere ejecutar — sin (a) calcular y mostrar el coste estimado primero y (b) confirmación explícita del usuario. El cliente en `client/odds_api.py` soporta `dry_run=True` por defecto en cualquier método que consuma cuota; solo gasta crédito real si se pasa `dry_run=False` explícitamente. Esta regla aplica tanto a Claude Code en sesiones futuras como a cualquier script del repo. Ver `scripts/verify_pinnacle.py` como ejemplo de referencia (confirmación interactiva antes de la única llamada que gasta crédito).

## Guardrail de control de versiones

No se deja acumular un working tree con muchos cambios sin confirmar. Cada incremento verificado (tests en verde, output real comprobado) se commitea de inmediato, en commits atómicos y pequeños — una sola cosa lógica por commit, mensaje con prefijo `feat/fix/docs/chore/test/refactor` que explica el porqué, no solo el qué. No se mezclan conceptos distintos en un mismo commit (p. ej. dependencias + feature + docs van en commits separados). Si al empezar una tarea nueva `git status` ya muestra cambios pendientes de una tarea anterior sin commitear, se resuelven primero (commit o se pregunta) antes de seguir añadiendo más encima. Esta regla aplica tanto a Claude Code en sesiones futuras como a cualquier colaborador del repo.

## Fuentes de datos ya evaluadas (no re-evaluar desde cero)

- **The Odds API** (the-odds-api.com — cuidado, no confundir con el competidor theoddsapi.com) es la fuente principal en evaluación. Su mecánica de créditos: coste = `[nº markets] × [nº regions]`; usar el parámetro `bookmakers` en vez de `regions` permite agrupar hasta 10 bookmakers como si fuera 1 sola región, lo cual es más eficiente cuando solo interesan Pinnacle + unas pocas soft books concretas. Los endpoints `/sports` y `/sports/{sport}/events` no consumen cuota.
- **Confirmado empíricamente (2026-07-06, `scripts/verify_pinnacle.py`):** Pinnacle SÍ está disponible en el tier gratuito — llamada real a `/v4/sports/soccer_fifa_world_cup/odds?bookmakers=pinnacle,bet365_uk&markets=h2h` devolvió datos de Pinnacle en los 6 eventos consultados. Coste real: 1 crédito por llamada, tal como predice la fórmula. Cuota real de la key confirmada por headers: 500 créditos/mes, 0 usados antes de este test. `bet365_uk` no apareció en ninguno de los 6 eventos del Mundial 2026 consultados — no confirma ni descarta su cobertura general, solo que no tenía precio publicado para esos eventos concretos en el momento del test.

## Qué está fuera de alcance salvo que se diga lo contrario explícitamente

- Modelos de probabilidad propios (Edge B).
- Componentes de ML/LLM para generar señales.
- Scraping con evasión anti-bot.
- Cualquier infraestructura de producción o preparada para escalar.
- Ejecución de apuestas reales o integración con cuentas de casas de apuestas.

## Cómo comunicarte con Edu durante el desarrollo

- Reporta números reales (créditos consumidos, tiempos, tamaños de dataset), no estimaciones presentadas como si fueran medidas.
- Si una tarea revela que un supuesto del roadmap era falso (p. ej. Pinnacle no está en el tier gratuito), decirlo de forma directa y proponer el ajuste, no seguir adelante como si no importara.
- Si hace falta tomar una decisión de arquitectura que no está cubierta aquí, preguntar antes de implementar, especialmente si implica coste recurrente o cambio de alcance.
