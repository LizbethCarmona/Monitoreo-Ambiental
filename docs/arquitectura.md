# Arquitectura de la solución — Monitoreo ambiental en tiempo real

> Complementa la sección 5 ("Arquitectura de la solución") del
> [Documento de Justificación](justificacion/Documento_Justificacion_Equipo_PC.pdf) y el
> [diagrama de clases UML](uml/diagrama_clases.puml).

## Diagrama de componentes y flujo de datos

```
┌─────────────────────┐      ┌───────────────────────────┐      ┌───────────────────────────┐
│ SensorHiloProductor  │      │     Cola Concurrente      │      │   ThreadPoolConsumidor     │
│ (N hilos, uno por    │ push │ (recurso compartido)      │ pop  │ (pool de hilos             │
│  sensor/fuente IoT)  ├─────►│  buffer: queue<Metrica>   ├─────►│  trabajadores)             │
│                      │      │  mtx + cv_productores/    │      │  - calcula promedios       │
│                      │      │  cv_consumidores          │      │  - evalúa umbrales         │
└──────────────────────┘      └───────────────────────────┘      └─────────────┬─────────────┘
                                                                                │ persiste
                                                                                ▼
                                                                  ┌───────────────────────────┐
                                                                  │     DatabaseManager        │
                                                                  │  (transacciones ACID:      │
                                                                  │  lectura + alerta)         │
                                                                  └─────────────┬─────────────┘
                                                                                │
                                                                                ▼
                                                                  ┌───────────────────────────┐
                                                                  │   MySQL: monitoreo_ambiental│
                                                                  │  sensores/lecturas/umbrales/│
                                                                  │  alertas                   │
                                                                  └─────────────┬─────────────┘
                                                                                │ consulta
                                                                                ▼
                                                                  ┌───────────────────────────┐
                                                                  │   APIServiceFastAPI        │
                                                                  │  getEstadoClima()/         │
                                                                  │  getAlertas()               │
                                                                  └─────────────┬─────────────┘
                                                                                │
                                                                                ▼
                                                                        Dashboard / clientes
```

## Descripción

Cada **sensor ambiental** (real o simulado) es atendido por un hilo productor
(`SensorHiloProductor`) que nunca escribe directamente en la base de datos ni en un
acumulador compartido: en su lugar empaqueta cada lectura como un objeto `MetricaSensor`
(`sensor_id`, `pm2.5`, `co2`, `tmp`, `timestamp`) y lo entrega a la **cola concurrente**, el
único recurso compartido entre productores y consumidores. La cola protege su buffer interno
con un `std::mutex` y usa dos `std::condition_variable` (una para avisar a los consumidores
que hay datos nuevos, otra para avisar a los productores cuando hay espacio libre), evitando
tanto la condición de carrera descrita en la sección 3.1 del documento de justificación como el
desperdicio de ciclos de CPU por *busy-waiting*.

Del otro lado, un **pool de hilos consumidores** (`ThreadPoolConsumidor`) extrae métricas de la
cola de forma segura, calcula agregados (promedios por sensor/ventana de tiempo) y evalúa si
algún valor supera los umbrales configurados (`docs/../src/database/schema.sql`, tabla
`umbrales`, con límites tomados de las normas NOM-025-SSA1-2021, NOM-010-STPS-2014 y
NOM-015-STPS-2001). Aquí ocurre el **procesamiento paralelo**: cada trabajador procesa un dato
de forma independiente y solo se sincroniza con el resto al leer/escribir el acumulador
compartido de agregados, protegido con mutex.

La **persistencia** ocurre exclusivamente en `DatabaseManager`, que agrupa en una sola
transacción ACID el `INSERT` de la lectura y, si corresponde, el `INSERT` de la alerta
asociada (ver `src/database/schema.sql` y el ejemplo de `START TRANSACTION ... COMMIT`), de
forma que dos hilos escribiendo al mismo tiempo nunca dejen una alerta huérfana ni una lectura
duplicada (restricción `UNIQUE KEY uq_sensor_momento`).

Finalmente, `APIServiceFastAPI` expone endpoints de solo lectura (`getEstadoClima`,
`getAlertas`) que consultan la base de datos para alimentar el dashboard y notificar a los
usuarios/autoridades (vínculo con ODS 11 y 13).

## Dónde ocurre cada preocupación

| Preocupación | Componente | Mecanismo |
|---|---|---|
| Concurrencia (ingesta) | `SensorHiloProductor` → `ColaConcurrente` | hilos productores + mutex/condition_variable |
| Concurrencia (procesamiento) | `ThreadPoolConsumidor` | pool de hilos + mutex sobre el acumulador de agregados |
| Persistencia | `DatabaseManager` → MySQL | transacciones ACID |
| Exposición de datos | `APIServiceFastAPI` | lecturas de solo consulta, no bloqueantes |

## Estado de implementación por sprint

Ver [docs/cronograma/cronograma.xlsx](cronograma/cronograma.xlsx) para el detalle semana a
semana. Resumen rápido:

- **Sprint 1 (semanas 1-2):** JSON de métricas, UML, simuladores IoT y núcleo concurrente
  (`src/cpp_ingestion/`) — en progreso.
- **Sprint 2 (semanas 3-4):** esquema de base de datos y persistencia transaccional
  (`src/database/`) — esquema y pruebas de carga ya avanzados.
- **Sprint 3 (semanas 5-6):** API REST (FastAPI) y WebSockets (`src/api_fastapi/`) — esqueleto
  inicial creado, pendiente motor de alertas y sockets.
- **Sprint 4 (semanas 7-8):** dashboard, pruebas de estrés, documentación final y
  sustentación.
