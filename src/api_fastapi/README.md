# API REST (`api_fastapi`)

Implementación de la clase `APIServiceFastAPI` del UML. Consulta en MySQL las lecturas que
ingresan por el núcleo C++ o por MQTT (`src/database/schema.sql`). La base de datos y las
consultas son reales; las lecturas de los simuladores no son mediciones físicas ni provienen
de un servicio meteorológico.

Si es la primera vez que ejecutas el proyecto, sigue el
[manual de usuario desde cero](../../docs/manual_usuario.md). Incluye la instalación de
MySQL Server sin Workbench, la creación inicial de la base de datos y el arranque de la demo
en Windows.

## Variables de entorno (conexión a MySQL)

Las mismas que usa `src/database/carga_concurrente.py` y el núcleo en C++:

```powershell
$env:MYSQL_HOST = "127.0.0.1"        # opcional, por defecto 127.0.0.1
$env:MYSQL_PORT = "3306"             # opcional, por defecto 3306
$env:MYSQL_USER = "monitoreo_app"    # recomendado: cuenta de aplicación con permisos mínimos
$clave = Read-Host "Contraseña MySQL" -AsSecureString
$env:MYSQL_PASSWORD = [System.Net.NetworkCredential]::new("", $clave).Password
$env:MYSQL_DATABASE = "monitoreo_ambiental"  # opcional
```

La base debe estar creada antes de iniciar el servicio, y la cuenta configurada requiere
permisos `SELECT` e `INSERT` sobre ese esquema. Usa una cuenta administradora únicamente para
crear el esquema y asignar esos permisos.

## Cómo correrlo

`app.main` contiene la aplicación FastAPI y sus rutas; `uvicorn` es el servidor ASGI que la
ejecuta y publica localmente. FastAPI sirve también los archivos estáticos del dashboard:
no hay un servidor Node.js separado. `mysql-connector-python` conecta la API a MySQL y
`paho-mqtt` implementa el cliente MQTT opcional. Docker Compose solo inicia Mosquitto para
la ruta MQTT; no ejecuta esta API ni MySQL. La ruta C++ escribe directamente en la misma base.

Instala el entorno una vez desde la raíz del repositorio:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r src\api_fastapi\requirements.txt
```

Después, desde la raíz, inicia la API en PowerShell:

```powershell
Set-Location src\api_fastapi
..\..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Luego abre `http://127.0.0.1:8000/docs` para la documentación interactiva (Swagger UI), o
prueba directamente:

- `GET /estado-clima` — equivalente a `APIServiceFastAPI.getEstadoClima()`: última lectura,
  mínimo/máximo del día UTC, promedios móviles de PM2.5 (24 h) y CO2 (8 h), y agregados
  observados por hora, calculados sobre la tabla `lecturas`. El historial horario incluye
  promedios separados de PM2.5 y temperatura, clasificación PM2.5 y fecha/hora UTC; contiene
  solo horas con lecturas dentro de las últimas 24 h.
- `GET /alertas` — equivalente a `APIServiceFastAPI.getAlertas()`: lee la tabla `alertas`
  (`WHERE atendida = 0`), devuelve el total de alertas no atendidas y una lista de hasta 20
  recientes. “Activa” aquí significa no marcada como atendida; no es un detector continuo de
  condiciones actuales.
- `GET /alertas/historial` — devuelve el total y una lista de hasta 100 alertas recientes,
  atendidas o no.
- `GET /salud` — valida MySQL y muestra el estado/conteos de MQTT sin exponer credenciales.
- `WS /ws/dashboard` — abre una conexión persistente entre el navegador y FastAPI. Al conectarse,
  envía un snapshot JSON de estado y alertas; después el hub comparte una consulta y difunde
  las nuevas instantáneas a todos los clientes aproximadamente cada 2 s. El cliente envía
  `ping` y recibe `pong` como latido. Este canal solo entrega datos al dashboard: no recibe
  publicaciones MQTT ni guarda en MySQL.
- `http://127.0.0.1:8000/dashboard/` — dashboard web (ver [src/dashboard/](../dashboard)),
  que recibe actualizaciones por WebSocket; usa REST para la carga inicial, el historial y
  consultas temporales si WebSocket se desconecta y está reconectando.

## Ingesta por MQTT

La API incluye un suscriptor MQTT 3.1.1. Al recibir un mensaje QoS 1, valida el topic, la
identidad, las tres métricas y un timestamp ISO-8601 con zona horaria; guarda lectura y alerta
puntual en una transacción MySQL; y confirma el mensaje MQTT solamente después del commit.
Un fallo transitorio de MySQL deja el mensaje sin ACK para permitir su reentrega por el broker.

1. Inicia un broker solo de desarrollo en localhost desde `src/api_fastapi`:

   ```powershell
   docker compose up -d mqtt
   ```

   Este broker de demostración permite mensajes anónimos y debe exponerse únicamente a la
   máquina local. En Windows se requiere Docker Desktop en ejecución con WSL instalado. Para
   una red real, configura un broker administrado con autenticación y TLS.
2. Define `$env:MQTT_ENABLED = "true"` y, si hacen falta, `MQTT_HOST`, `MQTT_PORT` y
   `MQTT_TOPIC` (`monitoreo/lecturas/+` por defecto). Para credenciales seguras usa
   `MQTT_USERNAME`, `MQTT_PASSWORD` y `MQTT_TLS_ENABLED=true`.
3. Inicia la API; comprueba `"mqtt.estado": "conectado"` en `/salud`.
4. Publica una lectura de prueba:

   ```powershell
   ..\..\.venv\Scripts\python.exe -m app.simulador_mqtt --sensores 3 --intervalo 2
   ```

El topic tiene la forma `monitoreo/lecturas/{sensor_id}` y el payload sigue
[docs/metricas_schema.json](../../docs/metricas_schema.json). El `sensor_id` del JSON debe
coincidir con el del topic. El publicador es un simulador de prueba, no un sensor físico.
Para apagar el simulador, pulsa `Ctrl+C` en su terminal. Para apagar el broker de desarrollo,
ejecuta `docker compose down` desde esta carpeta.

## Para ver datos cambiando en vivo

La API por sí sola solo lee lo que ya haya en la base de datos. Para ver el dashboard
actualizarse con valores nuevos, usa el simulador MQTT anterior o corre en paralelo el núcleo
concurrente C++ (`make run-continuo`). Ambos publican lecturas simuladas que el dashboard
recibe por WebSocket. MQTT es el canal para sensores conectados a un broker compatible.

## Pruebas automatizadas

Instala las dependencias de desarrollo una vez desde la raíz del repositorio:

```powershell
.\.venv\Scripts\python.exe -m pip install -r src\api_fastapi\requirements-dev.txt
```

Después ejecuta la suite desde `src\api_fastapi`. Para incluir la prueba contra un broker
Mosquitto real, inicia antes `docker compose up -d mqtt` y define
`$env:MQTT_TEST_BROKER = "127.0.0.1"`:

```powershell
Set-Location src\api_fastapi
..\..\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

## Nota técnica: `use_pure=True`

`db.py` fuerza la implementación pura en Python del conector (`use_pure=True`) en vez de su
extensión en C. Se detectó que la extensión en C puede crashear (access violation) en
Windows cuando uvicorn atiende varias peticiones concurrentes en hilos distintos del pool;
la versión pura es mas lenta pero segura para este caso de uso (pocas peticiones por
segundo).

## Alcance de las alertas y los datos

Las alertas puntuales se generan en cada lectura usando los límites aplicables a `lectura`.
La API presenta promedios móviles de 8 h y 24 h con sus propios límites y no los compara con
umbrales instantáneos. El esquema conserva únicamente alertas puntuales; límites de promedios
se muestran como métricas de referencia, no como eventos disparados. Valores por lectura de
PM2.5 y temperatura del aire son aproximaciones/provisionales: no equivalen a una certificación
regulatoria. La ubicación de la interfaz es fija hasta que los sensores aporten ubicación.
