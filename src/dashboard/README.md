# Dashboard web (`src/dashboard`)

Interfaz visual del proyecto: tarjeta de clima/calidad del aire actual, pronóstico de
temperatura por hora y panel de alertas activas. Replica el mockup de referencia acordado por
el equipo. Corresponde al componente "Dashboard" del diagrama de arquitectura
([docs/arquitectura.md](../../docs/arquitectura.md)) y adelanta el Sprint 4 (Semana 7).

## Cómo verlo

Se sirve automáticamente junto con la API (no es necesario un servidor aparte):

```bash
cd src/api_fastapi
uvicorn app.main:app --reload
```

Abre `http://127.0.0.1:8000/dashboard/` en el navegador.

## Cómo funciona

- HTML/CSS/JS plano (sin frameworks ni build step) para que cualquiera del equipo lo pueda
  editar sin instalar nada extra.
- `app.js` hace `fetch()` a `/estado-clima` y `/alertas` (montado como archivos estáticos
  dentro de la misma app de FastAPI, para evitar problemas de CORS) y repinta la interfaz
  cada 5 segundos (`REFRESCO_MS`), simulando actualización en tiempo real mientras no existe
  el WebSocket (Sprint 3, Semana 6).
- Los colores de los puntos (verde/amarillo/rojo) se calculan a partir de los campos
  `*_nivel` que ya vienen en la respuesta de la API (`normal` | `advertencia` | `critico`),
  el mismo vocabulario que usa `ThreadPoolConsumidor::evaluarUmbrales` en el núcleo
  concurrente de C++.

## Pendiente (próximos sprints)

- Reemplazar el polling por WebSocket para actualización push real.
- Historial de alertas (el enlace "Ver historial de alertas" es un placeholder).
- Conectar con datos reales de MySQL en lugar de los de ejemplo de `app/main.py`.
