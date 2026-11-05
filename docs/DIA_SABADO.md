# Guía del sábado 7 de noviembre — Tareas 4 y 5

Objetivo: tener **ambos CSV válidos subidos a la 1:00 pm** y usar el resto del tiempo en mejorar
y en contar la historia. Un CSV perfecto a las 3:05 no cuenta.

## Viernes (hoy/mañana)

- [ ] Responder **ROOM** al correo de Luke (si no, se pierde el cupo).
- [ ] Unirse a Slack y conseguir equipo (2 a 6 personas, **todos con cupo ya ofrecido**).
- [ ] Elegir nombre de equipo. El slug del CSV sale de ahí: `Data Wranglers` → `data-wranglers`.
- [ ] Crear el repo **público** vacío en GitHub y dar acceso a todos.
- [ ] En tu laptop: `pip install -r requirements.txt`, luego `bash scripts/run_all.sh --quick`.
      Si termina sin error con datos simulados, el sábado solo cambian los archivos.
- [ ] Probar `streamlit run app/app.py` y grabar 10 s de pantalla para confirmar que el grabador funciona.
- [ ] Preguntarle a Luke por correo (respuesta por escrito = sin riesgo):
  1. ¿Podemos usar un anuncio *For Sale* fechado antes del 31 de agosto de un depto que se vendió después?
     (Las reglas lo permiten tal como están escritas, pero mejor confirmarlo.)
  2. ¿Un solo `pitch.mp4` y `demo.mp4` cubren dos tareas, o esperan uno por tarea?
  3. ¿El archivo de alquileres pasados y el de ventas llegan cortados en la fecha de la tarea, o hay
     que filtrarlos? (El kit filtra de todos modos.)

## Sábado, antes de las 10 am

- [ ] Desayunar. Laptop y cargador. Claude Code con sesión iniciada.
- [ ] **Una persona** registra el equipo en el formulario de Google (integrantes + tareas 4 y 5).

## Roles (con 3–4 personas; con 2, se juntan 1+2 y 3+4)

| Rol | Hace | Subagente |
|---|---|---|
| 1. Datos | Revisa archivos, arregla `SCHEMA`, filtro por fecha | `data-engineer` |
| 2. Alquileres | Mejora la tarea 4 con el *held-out* | `rent-modeler` |
| 3. Valuación | Mejora la tarea 5 con el *held-out* | `valuation-modeler` |
| 4. Historia | notes.md, README, guiones, videos, revisión final | `storyteller-qa` |

## Cronograma

| Hora | Qué | Quién |
|---|---|---|
| 10:00 | Mesa, café, wifi, clonar repo, `pip install` | todos |
| 10:30 | Bienvenida y reto: escuchar si cambia alguna regla de las tareas 4 y 5 | todos |
| 11:00 | Llega la clave y los archivos por correo → `data/supplied/`, clave en `.env` | 1 |
| 11:05 | Pedir a Claude Code: *"usa data-engineer: imprime columnas, tipos, rango de fechas y 3 filas de cada archivo en data/supplied y corrige SCHEMA en src/config.py"* | 1 |
| 11:20 | Borrar `data/supplied/MOCK_DATA_DO_NOT_USE_FOR_PITCH.txt` y `data/mock_hidden/`. `python -m src.rents --quick` y `python -m src.valuation --quick` | 1 |
| 11:40 | **Primera versión real**: `bash scripts/run_all.sh`. Commit de los dos CSV + `report.html`. | 1 |
| 11:40–1:00 | Un cambio a la vez, medido con el *held-out*. Anotar lo que no funcionó. | 2, 3 |
| 11:40–1:00 | Mirar los resultados en `outputs/metrics_*.json` y elegir los 2–3 hallazgos | 4 |
| **1:00** | **Subir CSV válidos** (`python -m src.validate` en verde) y `report.html`. Esto ya es una entrega. | 1 |
| 1:00–2:00 | Últimas mejoras; a la 1:45 se congela el modelo | 2, 3 |
| 1:30–2:30 | Escribir notes.md y README, grabar `demo.mp4` (app + informe) y `pitch.mp4` | 4 (+ todos) |
| 2:30 | Revisión final con `storyteller-qa` (las 6 comprobaciones) | 4 |
| 2:45 | Último push. Nada después de las 2:50. | 1 |
| 3:00 | Cierre de entregas | |

## Si algo sale mal

| Problema | Plan B |
|---|---|
| Un archivo trae columnas distintas | Solo se toca `SCHEMA` en `src/config.py`; el cargador avisa qué falta |
| El pipeline completo tarda demasiado | `--quick` (4 snapshots en vez de 12) |
| El modelo no supera al mejor baseline en el *held-out* | Entregar el baseline ganador (la tabla lo muestra) y contarlo con honestidad en el informe |
| Falta tiempo para la tarea 5 | Entregar la versión `--quick`; los blancos cuentan como error, un valor razonable no |
| La API va lenta o da 429 | No hace falta: el kit funciona solo con los archivos entregados |
| Video > 95 MB | `ffmpeg -i in.mp4 -vf scale=-2:1080 -c:v libx264 -preset veryfast -crf 28 -c:a aac out.mp4` |

## Reglas que no se negocian

1. Tarea 4: nada posterior al **31/07/2026**. Tarea 5: nada posterior al **31/08/2026**. La API no filtra por fecha.
2. Al repo nunca van: la clave, los archivos entregados, la salida de la API, nada de `data/`.
3. Cada número del pitch sale de `outputs/metrics_*.json` y se anota en `pitch/numbers.md`.
4. La prueba de la tarea 5 son 227 ventas: diferencias de pocos puntos son suerte. No perseguirlas.
