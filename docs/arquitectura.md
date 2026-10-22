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

El sistema admite dos rutas de entrada que comparten MySQL: el productor simulado en C++
atraviesa la cola y el pool de consumidores; el suscriptor MQTT de FastAPI valida mensajes
QoS 1 y confirma la lectura con alerta puntual en una transacción. Clientes del dashboard
reciben snapshots por `WS /ws/dashboard`; un único publicador consulta MySQL cada dos segundos
y difunde el estado a todos los clientes conectados. El dashboard usa consultas REST periódicas
solo como compatibilidad durante la reconexión o mientras la API desplegada se actualiza.

**WebSocket** (`/ws/dashboard`) es el canal persistente entre el navegador y FastAPI para
actualizaciones del dashboard: al conectar, el navegador recibe un snapshot JSON con el estado
y las alertas; mientras hay clientes conectados, el hub consulta MySQL aproximadamente cada
dos segundos y difunde el snapshot compartido a todos ellos. El cliente envía `ping` cada
20 segundos y la API responde `pong` para comprobar que la conexión sigue viva. WebSocket no
transporta las publicaciones MQTT ni escribe en MySQL. REST carga el estado inicial y el
historial, y sirve como respaldo temporal mientras el cliente reconecta WebSocket.

Para el entorno de demostración MQTT, Docker Compose ejecuta únicamente Mosquitto como broker
local en el puerto 1883. MySQL, FastAPI y el dashboard se ejecutan por separado. La ruta C++
escribe directamente en MySQL y puede utilizarse sin iniciar Docker ni Mosquitto.

## Tecnologías y responsabilidades

| Pieza | Qué es y qué hace | Qué no hace |
|---|---|---|
| C++17 (`src/cpp_ingestion`) | Productores simulados, `std::thread`, cola bloqueante, pool de consumidores y escritura transaccional a MySQL mediante el conector C de MariaDB compatible con MySQL. | No se conecta al broker MQTT ni pasa por FastAPI para guardar la lectura. |
| Python + FastAPI (`src/api_fastapi/app`) | Implementa rutas REST, ingesta MQTT opcional, consultas y WebSocket. | FastAPI no es el servidor de procesos: Uvicorn inicia y mantiene la aplicación HTTP. |
| Uvicorn | Servidor ASGI que ejecuta FastAPI localmente, por defecto en `127.0.0.1:8000`. | No almacena datos ni crea MySQL. |
| MySQL 8 / InnoDB | Servidor y motor relacional que persisten sensores, lecturas, umbrales y alertas. | No lo inicia el Compose de Mosquitto; debe estar instalado/ejecutándose aparte. |
| MQTT / Mosquitto | MQTT es el protocolo publish/subscribe. Mosquitto es el broker que recibe publicaciones del simulador o dispositivo y las entrega al suscriptor MQTT de la API. | El broker transporta mensajes; no es la base de datos ni evalúa los umbrales del sistema. |
| Docker Desktop / Compose | Ejecuta el contenedor `eclipse-mosquitto:2` definido en `src/api_fastapi/compose.yaml`, con el puerto 1883 enlazado a localhost. | No empaqueta ni ejecuta FastAPI, MySQL o el dashboard. Solo se necesita en la ruta MQTT local. |
| HTML / CSS / JavaScript | Dashboard sin framework ni build: FastAPI sirve los archivos; REST carga estado/historial y WebSocket actualiza estado y alertas. | No necesita Node.js ni es un servicio separado. |

**Rutas de datos:** C++ → cola concurrente → consumidores → MySQL; o publicador MQTT →
Mosquitto → ingestor MQTT de FastAPI → MySQL. En ambas rutas, FastAPI consulta MySQL y entrega
el estado al dashboard por WebSocket/REST. Son lecturas sintéticas si se ejecuta un simulador;
los sensores físicos y su calibración no forman parte del prototipo.

Cada **sensor simulado** es atendido por un hilo productor
(`SensorHiloProductor`) que nunca escribe directamente en la base de datos ni en un
acumulador compartido: en su lugar empaqueta cada lectura como un objeto `MetricaSensor`
(`sensor_id`, `pm2.5`, `co2`, `tmp`, `timestamp`) y lo entrega a la **cola concurrente**, el
único recurso compartido entre productores y consumidores. La cola protege su buffer interno
con un `std::mutex` y usa dos `std::condition_variable` (una para avisar a los consumidores
que hay datos nuevos, otra para avisar a los productores cuando hay espacio libre), evitando
tanto la condición de carrera descrita en la sección 3.1 del documento de justificación como el
desperdicio de ciclos de CPU por *busy-waiting*.

Del otro lado, un **pool de hilos consumidores** (`ThreadPoolConsumidor`) extrae métricas de la
cola de forma segura, acumula estadísticas por sensor durante el proceso y evalúa si algún
valor puntual supera los umbrales de lectura configurados en `src/database/schema.sql` (tabla
`umbrales`). La API calcula los promedios móviles de 8 h y 24 h por separado y los compara con
sus propios límites. Las alertas persistidas actuales son puntuales. Los límites tienen las
fuentes y reservas descritas en el esquema; no todos aplican a lecturas puntuales. Aquí ocurre
el **procesamiento paralelo**: cada trabajador procesa un dato de forma independiente y solo
se sincroniza con el resto al leer/escribir el acumulador compartido de agregados, protegido
con mutex.

La **persistencia** ocurre exclusivamente en `DatabaseManager`, que agrupa en una sola
transacción ACID el `INSERT` de la lectura y, si corresponde, el `INSERT` de la alerta
asociada (ver `src/database/schema.sql` y el ejemplo de `START TRANSACTION ... COMMIT`), de
forma que dos hilos escribiendo al mismo tiempo nunca dejen una alerta huérfana ni una lectura
duplicada (restricción `UNIQUE KEY uq_sensor_momento`).

Finalmente, `APIServiceFastAPI` expone endpoints REST de consulta, ingesta MQTT y un endpoint
WebSocket (`/ws/dashboard`) que difunde snapshots basados en MySQL a los navegadores. El
simulador MQTT facilita validar el protocolo sin hardware; un dispositivo real debe publicar
el formato documentado y requiere calibración. La ubicación del panel se configura con
`CIUDAD_NOMBRE`; el prototipo no envía notificaciones a autoridades.

## Dónde ocurre cada preocupación

| Preocupación | Componente | Mecanismo |
|---|---|---|
| Concurrencia (ingesta) | `SensorHiloProductor` → `ColaConcurrente` | hilos productores + mutex/condition_variable |
| Concurrencia (procesamiento) | `ThreadPoolConsumidor` | pool de hilos + mutex sobre el acumulador de agregados |
| Persistencia | `DatabaseManager` → MySQL | transacciones ACID |
| Entrada de red | `IngestorMQTT` → MySQL | suscripción MQTT QoS 1, validación, commit antes del ACK |
| Actualizaciones del dashboard | `HubDashboard` → `WS /ws/dashboard` | canal persistente; snapshot JSON compartido de estado y alertas cada ~2 s, `ping`/`pong` |

## Estado de implementación por sprint

Ver [docs/cronograma/cronograma.xlsx](cronograma/cronograma.xlsx) para el detalle semana a
semana. Resumen rápido (actualizado tras conectar el flujo extremo a extremo de verdad):

- **Sprint 1 (semanas 1-2):** JSON de métricas, UML, simuladores IoT y núcleo concurrente
  (`src/cpp_ingestion/`) — hecho.
- **Sprint 2 (semanas 3-4):** esquema de base de datos y persistencia transaccional
  (`src/database/`) — hecho; `DatabaseManager` ya inserta lecturas y alertas reales en MySQL
  con transacciones `START TRANSACTION`/`COMMIT`/`ROLLBACK` (adelantado desde la Semana 4).
- **Sprint 3 (semanas 5-6):** API REST (FastAPI) consultando MySQL (`src/api_fastapi/`) y
  dashboard (`src/dashboard/`) — demo funcional; la API incluye suscriptor MQTT opcional,
  consulta histórica y WebSocket para los clientes.
- **Sprint 4 (semanas 7-8):** dashboard, pruebas concurrentes/de persistencia, manual y guion de
  demostración — código/documentación entregados. Las pruebas que requieren MySQL se ejecutan
  con credenciales autorizadas y su resultado debe quedar registrado.

### Cómo correr el flujo completo

Ver el [manual de usuario](manual_usuario.md) y la sección "Cómo correr la demo de extremo a
extremo" del [README](../README.md): el núcleo C++ o el simulador MQTT insertan lecturas en
MySQL mientras FastAPI comparte snapshots al dashboard por WebSocket.
