# Guion de demostración

## Orden de ejecución

1. Confirma MySQL en ejecución, que existe el esquema `monitoreo_ambiental` y que la API usa
   una cuenta de aplicación; configura `MYSQL_*` en la terminal PowerShell desde la que se
   iniciará Uvicorn. Las variables no se transfieren entre terminales; si Uvicorn ya estaba
   activo en otra, detenlo con `Ctrl+C` y vuelve a iniciarlo en la terminal configurada.
2. Para la demostración local MQTT, inicia Docker Desktop y el broker Mosquitto (`docker compose
   up -d mqtt` desde `src/api_fastapi`). En el despliegue multiusuario que se demuestra al equipo,
   Compose inicia FastAPI, MySQL persistente, Mosquitto y el simulador; Tailscale Serve publica
   HTTPS solo al tailnet autorizado. Consulta la
   [guía de acceso privado](../src/api_fastapi/README.md#compartir-de-forma-privada-con-tailscale).
   La ruta C++ directa a MySQL no requiere Docker.
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

## Demostración multiusuario

Abre el dashboard desde dos dispositivos autorizados en el tailnet e inicia sesión con dos
cuentas distintas. Muestra que ambos reciben el estado compartido por WebSocket y que cerrar
sesión en uno no invalida la sesión del otro. Una petición anónima a las rutas de datos debe
responder `401`. Aclara que Tailscale limita quién puede llegar al servicio y que la aplicación
mantiene la autenticación individual; no se trata de una URL pública.

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
