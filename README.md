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
│   ├── cpp_ingestion/    # Núcleo concurrente (C++17): colas, hilos, umbrales, persistencia
│   ├── database/         # Esquema MySQL, datos de prueba y pruebas de carga concurrente
│   └── api_fastapi/      # API REST (FastAPI) — esqueleto inicial
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

## Cómo correr cada parte

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
semana a semana (9 semanas, 4 sprints, presentación final el 23 de noviembre).
