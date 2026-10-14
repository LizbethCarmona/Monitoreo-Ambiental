# API REST (`api_fastapi`)

Esqueleto inicial de la clase `APIServiceFastAPI` del UML. Implementación completa prevista
para el Sprint 3 (Semanas 5-6): motor de alertas, consultas históricas reales a MySQL y
WebSockets para transmisión en vivo.

## Cómo correrlo

```bash
cd src/api_fastapi
python -m venv .venv
source .venv/bin/activate        # en Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Luego abre `http://127.0.0.1:8000/docs` para la documentación interactiva (Swagger UI), o
prueba directamente:

- `GET /estado-clima` — equivalente a `APIServiceFastAPI.getEstadoClima()`
- `GET /alertas` — equivalente a `APIServiceFastAPI.getAlertas()`
- `GET /salud` — chequeo simple de disponibilidad
- `http://127.0.0.1:8000/dashboard/` — dashboard web (ver
  [src/dashboard/](../dashboard)), sirve la misma interfaz que el mockup de referencia del
  equipo, consumiendo los dos endpoints de arriba con polling cada 5 segundos.

## Estado actual

Los endpoints devuelven datos de ejemplo (ver `_ESTADO_CLIMA_EJEMPLO` / `_ALERTAS_EJEMPLO` en
`app/main.py`), con el mismo esquema que espera el dashboard. Pendiente conectar con
`src/database/schema.sql` una vez que el núcleo concurrente en C++ (`src/cpp_ingestion/`)
esté escribiendo en MySQL real.
