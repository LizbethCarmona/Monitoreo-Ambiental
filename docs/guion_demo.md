# Guion de demostración

## Orden de ejecución

1. Confirma MySQL en ejecución, que existe el esquema `monitoreo_ambiental` y que la API usa
   una cuenta de aplicación; configura `MYSQL_*` solo en la terminal local.
2. Para la demostración MQTT, inicia Docker Desktop y el contenedor del broker Mosquitto desde
   `src/api_fastapi` (`docker compose up -d mqtt`). Este contenedor solo recibe/publica mensajes
   MQTT; no ejecuta la API, MySQL ni el dashboard. La ruta C++ directa a MySQL no requiere Docker.
3. Enciende FastAPI con `MQTT_ENABLED=true`; revisa `/salud` y comprueba MySQL y MQTT.
4. Abre `/dashboard/`; comprueba `En vivo · WebSocket` y observa las actualizaciones. Explica
   que la página abre un canal persistente con FastAPI y recibe por él un snapshot JSON del
   estado y las alertas aproximadamente cada 2 s; WebSocket solo actualiza la pantalla, no
   recibe MQTT ni guarda datos.
5. En otra terminal, inicia `python -m app.simulador_mqtt --sensores 3 --intervalo 2`.
   Observa cómo cambian las lecturas y aparecen alertas puntuales cuando se rebasan límites.
6. Detén el publicador MQTT con `Ctrl+C`. En MSYS2 UCRT64 corre `make test` desde `src/cpp_ingestion` para
   mostrar la condición de carrera reproducida sin mutex, el resultado protegido y la cola con
   productores/consumidores concurrentes.
7. Si la conexión MySQL de prueba está autorizada, corre la carga de persistencia documentada
   en el manual y muestra el conteo verificado por la misma ejecución.
8. Abre el historial de alertas desde el dashboard. Explica que “activas” son las alertas aún
   no atendidas, mientras que el historial incluye atendidas y no atendidas; ambas se generan
   por lecturas puntuales. Los promedios móviles se muestran aparte y no crean alertas guardadas.

## Recorrido MQTT comprobado en Windows

El 13 de octubre de 2026 se verificó localmente que `/salud` reportara la conexión a MySQL y
MQTT, que el simulador publicara lecturas MQTT para tres sensores y que las lecturas pudieran
consultarse en `/estado-clima` y verse en el dashboard por WebSocket. Es una comprobación
funcional manual con datos sintéticos; no sustituye la prueba de carga concurrente SQL ni
demuestra mediciones de sensores físicos.

## Explicación de un minuto

El proyecto recibe datos de sensores en dos rutas. Para la demo, C++ produce lecturas sintéticas
y las sincroniza mediante una cola bloqueante y varios consumidores. La ruta IoT se suscribe a
`monitoreo/lecturas/+` por MQTT y valida el payload antes de confirmar su transacción. Ambas
rutas almacenan datos en MySQL. FastAPI consulta esa base y difunde el estado compartido a los
navegadores por WebSocket. La interfaz es en vivo, aunque los valores del simulador no son
mediciones físicas ni un pronóstico meteorológico.

WebSocket es el canal de salida entre FastAPI y el dashboard: transporta snapshots de estado y
alertas que FastAPI consulta de MySQL. REST carga inicialmente el dashboard y su historial; si
WebSocket se interrumpe, el navegador consulta REST temporalmente mientras intenta reconectar.

## Evidencia que se debe anotar el día de la presentación

- Fecha, versión/commit demostrado y nombres de responsables.
- Resultado y tiempo de la prueba C++ de concurrencia.
- Lecturas publicadas/guardadas por MQTT y resultado del endpoint `/salud`.
- Número esperado y real de filas en la carga MySQL; alertas huérfanas.
- Confirmación de la actualización simultánea en dos clientes WebSocket.
- Incidencias observadas y resolución.
