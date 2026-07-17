"""Página Guía: cómo leer el dashboard sin saber estadística ni apuestas.

Texto plano y sin jerga. Cada gráfico tiene además un desplegable
':material/help: Cómo leer este gráfico' junto a él con la versión corta.
"""

import streamlit as st

GUIDE = """
## La idea del proyecto, en una frase

Pinnacle es la casa de apuestas que mejor pone los precios; las casas "soft"
(williamhill, betvictor, winamax, marathonbet) tardan más en reaccionar.
Queremos comprobar con datos si esos retrasos dejan precios "demasiado buenos"
que se puedan aprovechar.

## Los cuatro conceptos que hacen falta

**Cuota**: lo que paga una apuesta. Cuota 2.00 = si aciertas, doblas.
Cuanto más alta la cuota para el mismo resultado, mejor para ti.

**Cierre de Pinnacle**: el último precio de Pinnacle justo antes de empezar el
partido. Es la mejor estimación disponible del precio "correcto", porque a esa
hora Pinnacle ya ha absorbido todo el dinero informado. Lo usamos como vara de
medir. Solo nos fiamos del cierre si lo capturamos en los **últimos 15
minutos** antes del partido ("benchmark válido").

**CLV** (Closing Line Value): compara el precio que capturamos en una casa
soft con el cierre de Pinnacle, en porcentaje.
- CLV **+2%** = el precio soft era un 2% mejor que el cierre. Bien.
- CLV **−5%** = era un 5% peor. Lo normal (las casas cobran margen).
- Batir al cierre de forma **consistente** es la señal aceptada de que una
  estrategia de apuestas tiene ventaja real, aunque a corto plazo se pierda.

**Muestra**: cuántos CLV hemos podido medir. Con pocos datos cualquier
resultado puede ser casualidad; la meta mínima del POC es **100**.

## Página "Go / No-Go"

Responde a LA pregunta del proyecto: ¿hay ventaja o no?

- **Fila de números de arriba (KPIs)**: cuántos CLV llevamos medidos, su
  promedio global, el hit-rate (% de capturas que batieron al cierre), cuántos
  días llevamos capturando y cuántos partidos tienen cierre fiable.
- **CLV medio por soft book**: el veredicto por casa. Barras por debajo de 0 =
  sus precios son peores que el cierre = sin ventaja. La rayita negra es el
  margen de error; mientras cruce el 0, el veredicto de esa casa no es firme.
- **Distribución de CLV**: en vez del promedio, TODOS los casos uno a uno.
  Sirve para ver si dentro de un promedio malo se esconde una minoría de
  capturas buenas (la "cola" a la derecha del 0).
- **CLV por horizonte al kickoff**: ¿los precios buenos aparecen 24h antes del
  partido, o en la última hora? Si alguna franja horaria vive por encima de 0,
  esa es la ventana donde apostar.
- **CLV por deporte**: lo mismo separado por competición, porque fútbol (3
  resultados posibles) y béisbol (2) no se calculan igual y mezclarlos engaña.
- **Crecimiento de la muestra**: cuánta evidencia acumulamos por día y cuánto
  falta para la meta de 100.

## Página "Trayectorias"

Zoom a un partido concreto. Elige evento y resultado (outcome) y verás:

- **Cuota soft vs cierre Pinnacle**: cómo fue moviéndose el precio de cada
  casa a medida que se acercaba el partido (el tiempo avanza hacia la
  derecha). La línea discontinua es el cierre de Pinnacle: los momentos en que
  una casa está POR ENCIMA son los precios que buscamos.
- **CLV a lo largo del tiempo**: la misma película traducida a "% mejor o peor
  que el cierre".

El filtro "Con CLV válido" enseña solo partidos ya cerrados con benchmark
fiable; "Todos" incluye los futuros (su línea de cierre aún puede moverse).

## Página "Operaciones"

Salud del sistema de captura — si esto falla, los análisis cojean.

- **Salud de capturas (mapa de calor)**: un cuadrado por día y deporte. Oscuro
  = día completo (8 capturas), claro = incompleto, vacío = día sin capturar.
- **Crecimiento de capturas**: total de precios guardados por día; debe subir
  siempre. Un tramo plano = día perdido.
- **Gaps detectados**: los huecos concretos, con fecha y duración.
- **Próximas capturas programadas**: lo que el sistema planea capturar y
  cuándo (consultarlo no gasta créditos de la API).
- **Tablas de datos**: los CLV calculados y las cuotas crudas tal cual se
  capturaron, con filtros. Para auditar cualquier número que veas en los
  gráficos.

## Cómo leer el margen de error (la rayita negra)

Aparece en varios gráficos y es lo más importante para no engañarse: es el
rango donde casi seguro (95%) está el valor real. Regla práctica:

- Rayita **entera por encima de 0** → ventaja real detectada.
- Rayita **entera por debajo de 0** → confirmado que no hay ventaja ahí.
- Rayita **cruzando el 0** → aún no se sabe; hacen falta más datos.
"""


def render() -> None:
    st.title("Guía: cómo leer este dashboard")
    st.caption(
        "Para leerla junto a los gráficos: cada uno tiene también un desplegable "
        "':material/help: Cómo leer este gráfico' con la versión corta."
    )
    st.markdown(GUIDE)
