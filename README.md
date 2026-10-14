# Monitoreo Ambiental en Tiempo Real

Sistema concurrente de monitoreo ambiental — Equipo 2, Programación Concurrente,
UVM Campus San Rafael. Vinculado a los **ODS 11** (Ciudades y comunidades sostenibles) y
**ODS 13** (Acción por el clima): ingesta simultánea de N sensores y procesamiento paralelo
de agregados con detección de umbrales de contaminación.

## Equipo

| Rol Scrum | Integrante |
|---|---|
| Product Owner | Ríos Olivares César Antonio |
| Scrum Master | Carmona Orea Lizbeth |
| Dev Team (Base de Datos) | Delgadillo Escartín Eduardo Abraham |
| Dev Team (Núcleo concurrente) | Flores Teja Axel, Carmona Orea Lizbeth |
| Dev Team (Servicio/Red) | Cucchi Villegas Samael, Vázquez Rodríguez Rodrigo Enrique |

## Documentación

- [Documento de Justificación del Proyecto](docs/justificacion/Documento_Justificacion_Equipo_PC.pdf)
- [Reporte Técnico de Métricas JSON](docs/reportes/Reporte_Tecnico_Metricas_JSON.pdf) y su
  esquema vivo en [docs/metricas_schema.json](docs/metricas_schema.json)
- [Diagrama de clases UML](docs/uml/diagrama_clases.puml) ([PDF](<docs/uml/Clase UML.pdf>))
- [Arquitectura de la solución](docs/arquitectura.md) (componentes, flujo de datos,
  dónde ocurre la concurrencia y la persistencia)
- [Cronograma del proyecto](docs/cronograma/cronograma.xlsx) (9 semanas, 4 sprints)
- [Convenciones de ramas y commits](CONTRIBUTING.md)

## Estructura del repositorio

```
.
├── docs/                 # Documentación, UML, JSON de métricas, cronograma
├── src/
│   ├── cpp_ingestion/    # Núcleo concurrente (C++17): colas, hilos, umbrales, persistencia real en MySQL
│   ├── database/         # Esquema MySQL, datos de prueba y pruebas de carga concurrente
│   ├── api_fastapi/      # API REST (FastAPI) — consulta MySQL real
│   └── dashboard/        # Dashboard web (HTML/CSS/JS), servido por la API
└── CONTRIBUTING.md
```

## Arquitectura (resumen)

```
SensorHiloProductor (N hilos) --push--> ColaConcurrente --pop--> ThreadPoolConsumidor
                                  (mutex + condition_variable)        |
                                                                       v
                                                              DatabaseManager (MySQL, ACID)
                                                                       |
                                                                       v
                                                             APIServiceFastAPI --> Dashboard
```

Ver el detalle completo en [docs/arquitectura.md](docs/arquitectura.md).

## Cómo correr el sistema completo (de verdad, extremo a extremo)

1. Crea el esquema en MySQL (una sola vez): `mysql -u root -p < src/database/schema.sql`.
2. Define `$env:MYSQL_PASSWORD` (y opcionalmente `MYSQL_HOST`/`MYSQL_USER`/`MYSQL_DATABASE`
   si no usas los valores por defecto) — la misma variable la usan el núcleo en C++, la API y
   `src/database/carga_concurrente.py`.
3. Corre el núcleo concurrente en modo continuo (alimenta MySQL con lecturas reales cada
   pocos segundos): `cd src/cpp_ingestion && make run-continuo`.
4. En otra terminal, corre la API + dashboard: `cd src/api_fastapi && uvicorn app.main:app --reload`.
5. Abre `http://127.0.0.1:8000/dashboard/`: verás temperatura, PM2.5, CO2 y alertas **reales**,
   leídos de MySQL, cambiando cada pocos segundos a medida que el núcleo en C++ inserta
   nuevas lecturas.

Ver el README de cada carpeta para el detalle (variables de entorno, cómo instalar el
conector de MySQL, etc.).

## Cómo correr cada parte por separado

- **Núcleo concurrente (C++):** ver [src/cpp_ingestion/README.md](src/cpp_ingestion/README.md)
  (`make run-demo`, `make test`).
- **Base de datos (MySQL + pruebas de carga):** ver
  [src/database/README.md](src/database/README.md).
- **API (FastAPI):** ver [src/api_fastapi/README.md](src/api_fastapi/README.md)
  (`uvicorn app.main:app --reload`).
- **Dashboard web:** se sirve automáticamente junto con la API en
  `http://127.0.0.1:8000/dashboard/` (ver [src/dashboard/](src/dashboard)).

## Estado del proyecto

Ver [docs/cronograma/cronograma.xlsx](docs/cronograma/cronograma.xlsx) para el detalle
semana a semana (9 semanas, 4 sprints, presentación final el 23 de noviembre). El flujo
extremo a extremo (hilos productores → cola concurrente → pool de hilos → MySQL real → API
→ dashboard) ya funciona de principio a fin, adelantado respecto al cronograma original.
