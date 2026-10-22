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
| Dev Team (Base de Datos) | Delgadillo Escartín Eduardo Abraham, Gutiérrez Ponce Sebastián |
| Dev Team (Núcleo concurrente) | Flores Teja Axel, Carmona Orea Lizbeth |
| Dev Team (Servicio/Red) | Cucchi Villegas Samael, Vázquez Rodríguez Rodrigo Enrique |

## Documentación

- **¿Primera vez con el proyecto?** Empieza por el
  [manual de usuario desde cero](docs/manual_usuario.md): instalación de Python y MySQL sin
  Workbench, preparación de la base de datos, ejecución de la demo y solución de problemas.
- [Documento de Justificación del Proyecto](docs/justificacion/Documento_Justificacion_Equipo_PC.pdf)
- [Reporte Técnico de Métricas JSON](docs/reportes/Reporte_Tecnico_Metricas_JSON.pdf) y su
  esquema vivo en [docs/metricas_schema.json](docs/metricas_schema.json)
- [Diagrama de clases UML en PlantUML](docs/uml/diagrama_clases.puml) (fuente editable y
  actualizada; el [PDF](<docs/uml/Clase UML.pdf>) es una exportación anterior y podría no
  reflejar los últimos cambios del modelo)
- [Arquitectura de la solución](docs/arquitectura.md) (componentes, flujo de datos,
  dónde ocurre la concurrencia y la persistencia)
- [Cronograma del proyecto](docs/cronograma/cronograma.xlsx) (9 semanas, 4 sprints)
- [Convenciones de ramas y commits](CONTRIBUTING.md)

## Estructura del repositorio

```
.
├── docs/                 # Documentación, UML, JSON de métricas, cronograma
├── src/
│   ├── cpp_ingestion/    # Núcleo concurrente (C++17): simulación, colas, hilos y persistencia MySQL
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

## Qué tecnologías se usan

| Tecnología o componente | Para qué se usa | ¿Siempre se necesita? |
|---|---|---|
| C++17, `std::thread`, mutex y cola concurrente | Simular productores y procesar lecturas en paralelo; guardar resultados en MySQL. | No para la demo MQTT; es una ruta de ingesta alternativa. |
| Python, FastAPI y Uvicorn | FastAPI implementa la API; Uvicorn la ejecuta como servidor web local. La API consulta MySQL, recibe MQTT opcionalmente y sirve el dashboard. | Sí para mostrar el dashboard y consultar los datos. |
| MySQL Server | Base de datos persistente: sensores, lecturas, umbrales y alertas. | Sí para el flujo completo; no lo ejecuta Docker Compose. |
| MQTT y Mosquitto | MQTT es el protocolo de mensajería; Mosquitto es el broker que recibe y reenvía mensajes MQTT. | Solo para usar la ruta MQTT. |
| Docker Desktop y Docker Compose | Docker ejecuta el contenedor de Mosquitto descrito en `src/api_fastapi/compose.yaml`. No contiene la API, MySQL ni el dashboard. | Solo para el broker local de la ruta MQTT. |
| HTML, CSS y JavaScript | Interfaz servida por FastAPI. Al abrirla, REST carga los datos iniciales; después, la conexión WebSocket persistente recibe de la API el estado y las alertas aproximadamente cada 2 s. REST también consulta el historial y sirve de respaldo si WebSocket se desconecta. | Sí para ver la interfaz; no requiere Node.js ni un paso de compilación. |

Las dos rutas de entrada son alternativas: **simulador C++ → cola/hilos → MySQL** o
**simulador/publicador MQTT → Mosquitto → API FastAPI → MySQL**. Ambas escriben en la misma
base; después la API entrega los datos al dashboard. La ruta C++ no pasa por el broker ni por
la API para guardar lecturas. Los simuladores producen datos sintéticos: el proyecto no incluye
hardware físico ni consulta un servicio meteorológico. Consulta [la arquitectura detallada](docs/arquitectura.md)
y el [manual desde cero](docs/manual_usuario.md) para conocer requisitos, comandos y límites.

**¿Qué hace WebSocket?** Es el canal persistente entre el navegador y FastAPI para enviar al
dashboard el estado y las alertas nuevos sin que la página tenga que pedirlos continuamente.
La API consulta MySQL y difunde un snapshot compartido aproximadamente cada 2 s. WebSocket no
recibe las publicaciones MQTT ni guarda datos; eso corresponde al ingestor y a MySQL.

## Cómo correr la demo de extremo a extremo

En Windows, con MySQL en ejecución y el esquema `monitoreo_ambiental` creado, abre una
terminal PowerShell en `src\api_fastapi`. Para la ruta MQTT, inicia Docker Desktop y el
contenedor local de Mosquitto con `docker compose up -d mqtt`; Docker ejecuta solo ese broker,
no MySQL, FastAPI ni el dashboard. Configura la cuenta MySQL de aplicación, habilita
`MQTT_ENABLED=true` y arranca FastAPI. En otra terminal, publica lecturas sintéticas con
`python -m app.simulador_mqtt --sensores 3 --intervalo 2`. Abre `/dashboard/`; verifica el
estado en `/salud` y las lecturas guardadas en `/estado-clima`. Los comandos completos están
en la [guía de ingesta MQTT y API](src/api_fastapi/README.md).

El núcleo C++ es una ruta de ingesta simulada independiente; sus requisitos y comandos están
en [su guía](src/cpp_ingestion/README.md). Si usas únicamente la ruta C++, no necesitas iniciar
Docker ni Mosquitto. El broker MQTT anónimo está limitado a desarrollo en localhost.

> **Alcance de la demo:** MySQL, MQTT y WebSocket son integraciones ejecutables. Las lecturas
> de demostración son sintéticas y se generan con los simuladores C++/MQTT; la integración de
> sensores físicos no forma parte del proyecto. No se consulta un servicio meteorológico. La
> ubicación mostrada es una etiqueta configurable (`CIUDAD_NOMBRE`), no una ubicación calculada
> a partir de sensores.

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
semana a semana (9 semanas, 4 sprints, presentación final el 23 de noviembre). La demo
funcional cubre productores simulados → cola concurrente → pool de consumidores → MySQL →
API REST → dashboard WebSocket. La implementación también ofrece una suscripción MQTT opcional
para dispositivos compatibles y conserva un simulador para demostración sin hardware. El
historial muestra hasta 100 alertas recientes; los promedios móviles se consultan con sus
umbrales diferenciados. La prueba MySQL concurrente de 10 000 intentos pasó el 14 de octubre
de 2026; la interpretación y alcance de los umbrales están documentados en el
[informe de pruebas](docs/informe_pruebas.md). La entrega presencial sigue su fecha académica programada: el proyecto
prepara su guion de demostración, pero no puede marcar como celebrada una sesión futura.

La instancia MySQL local usada para la demostración quedó con cero lecturas y alertas tras la
limpieza confirmada el 15 de octubre de 2026; las cifras de carga anteriores se conservan como
evidencia histórica. El dashboard seguirá vacío mientras no se ejecuten los simuladores.

Documentos de cierre: [manual de usuario](docs/manual_usuario.md), [guion de demo](docs/guion_demo.md),
y [informe de pruebas](docs/informe_pruebas.md).
