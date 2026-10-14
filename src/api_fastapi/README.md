# API REST (`api_fastapi`)

Implementación de la clase `APIServiceFastAPI` del UML, consultando **datos reales** de
MySQL (`src/database/schema.sql`), adelantado respecto al cronograma (previsto para el
Sprint 3, Semanas 5-6; falta el motor de alertas instantáneo y los WebSockets).

## Variables de entorno (conexión a MySQL)

Las mismas que usa `src/database/carga_concurrente.py` y el núcleo en C++:

```powershell
$env:MYSQL_HOST = "127.0.0.1"        # opcional, por defecto 127.0.0.1
$env:MYSQL_PORT = "3306"             # opcional, por defecto 3306
$env:MYSQL_USER = "root"             # opcional, por defecto root
$env:MYSQL_PASSWORD = "tu_clave"     # obligatoria
$env:MYSQL_DATABASE = "monitoreo_ambiental"  # opcional
```

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

- `GET /estado-clima` — equivalente a `APIServiceFastAPI.getEstadoClima()`: última lectura,
  min/máx del día, promedio de PM2.5 de 24 h y pronóstico por hora, todo calculado con
  consultas `SELECT`/`AVG`/`GROUP BY` reales sobre la tabla `lecturas`.
- `GET /alertas` — equivalente a `APIServiceFastAPI.getAlertas()`: lee la tabla `alertas`
  (`WHERE atendida = 0`).
- `GET /salud` — valida que la API puede conectarse a MySQL.
- `http://127.0.0.1:8000/dashboard/` — dashboard web (ver [src/dashboard/](../dashboard)),
  consumiendo los dos endpoints de arriba con polling cada 5 segundos.

## Para ver datos cambiando en vivo

La API por sí sola solo lee lo que ya haya en la base de datos. Para ver el dashboard
actualizarse con valores nuevos, corre en paralelo el núcleo concurrente en modo continuo
(ver [src/cpp_ingestion/README.md](../cpp_ingestion/README.md), `make run-continuo`), que
inserta lecturas reales cada pocos segundos.

## Nota técnica: `use_pure=True`

`db.py` fuerza la implementación pura en Python del conector (`use_pure=True`) en vez de su
extensión en C. Se detectó que la extensión en C puede crashear (access violation) en
Windows cuando uvicorn atiende varias peticiones concurrentes en hilos distintos del pool;
la versión pura es mas lenta pero segura para este caso de uso (pocas peticiones por
segundo).

## Pendiente (próximos sprints)

- Sprint 3 (Semana 5): motor de alertas que evalúe umbrales al momento de la escritura (hoy
  lo hace `ThreadPoolConsumidor` en C++; la API solo lee lo ya calculado).
- Sprint 3 (Semana 6): reemplazar el polling del dashboard por WebSockets.
- Agregar una columna de ciudad/ubicación a `sensores` si el proyecto pasa a ser
  multi-ciudad (hoy `CIUDAD_NOMBRE` está fijo en `app/main.py`).
