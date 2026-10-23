# Núcleo concurrente (`cpp_ingestion`)

Implementación en C++17 del diagrama de clases UML
([docs/uml/diagrama_clases.puml](../../docs/uml/diagrama_clases.puml)):
`MetricaSensor`, `ColaConcurrente`, `SensorHiloProductor`, `ThreadPoolConsumidor` y
`DatabaseManager`. Corresponde a la Semana 2 del cronograma ("núcleo concurrente y
sincronización").

## Estructura

```
cpp_ingestion/
├── include/                      # Headers (MetricaSensor, ColaConcurrente, Umbrales, ...)
├── src/                          # Implementación + main.cpp (demo end-to-end)
├── tests/                        # Pruebas de concurrencia (ver abajo)
├── iot_lua_sim/                  # Prototipo inicial de la Semana 1 (ver su propio README)
└── Makefile
```

## Cómo funciona (resumen)

Es una ruta independiente de la ingesta MQTT: no necesita ejecutar FastAPI para escribir
lecturas ni requiere Docker/Mosquitto. Sí necesita MySQL iniciado, el esquema preparado, un
compilador C++17 y el conector C compatible con MySQL descrito abajo. FastAPI puede ejecutarse
al mismo tiempo para consultar la base y mostrar en el dashboard las lecturas C++.

1. `SensorHiloProductor` simula N sensores (uno por `std::thread`) generando lecturas
   sintéticas y las empuja a una `ColaConcurrente` compartida.
2. `ColaConcurrente` es una *blocking queue* con `std::mutex` + 2 `std::condition_variable`:
   bloquea productores si está llena y consumidores si está vacía, sin *busy-waiting*.
3. `ThreadPoolConsumidor` lanza un pool de hilos que extraen de la cola, actualizan un
   acumulador compartido (protegido con mutex) y evalúan los umbrales puntuales cargados desde
   `src/database/schema.sql`. Los umbrales de promedio de 8 h/24 h son distintos y los calcula
   la API; el consumidor no genera alertas por esas ventanas.
4. `DatabaseManager` persiste cada lectura (y su alerta, si aplica) como una única
   transacción real de MySQL (`START TRANSACTION` / `COMMIT` / `ROLLBACK`), usando el
   conector C de MariaDB (protocolo compatible con MySQL 8). Esto ya está conectado de
   verdad contra `src/database/schema.sql` (adelantado respecto al cronograma, que lo
   planeaba para la Semana 4). El consumidor C++ solo escribe en MySQL: FastAPI consulta esas
   filas y envía al navegador snapshots de estado y alertas por WebSocket aproximadamente cada
   2 s. WebSocket no forma parte de la ruta de escritura C++.

La entrada MQTT está implementada como una segunda ruta ejecutable en la API
(`IngestorMQTT`); consulta la guía [API/MQTT](../api_fastapi/README.md). `SensorHiloProductor`
sigue siendo el simulador concurrente C++; no hace falta reemplazarlo para demostrar MQTT.
La ruta C++ escribe directamente en MySQL y no requiere Docker ni Mosquitto. Para la demo local,
Docker Compose puede ejecutar el broker MQTT; para el despliegue público del dashboard, Compose
también define FastAPI y Caddy con HTTPS. Consulta la
[guía de despliegue multiusuario](../api_fastapi/README.md#despliegue-multiusuario-en-internet).

## Compilar y correr

> **Windows:** el MinGW.org clásico no soporta `std::thread`. Se necesita un mingw-w64 (por
> ejemplo MSYS2 `ucrt64`) o compilar directamente en Linux/WSL, que es donde el equipo
> planea correr el sistema finalmente (ver pregunta abierta en el Documento de
> Justificación, sección final).
>
> Con MSYS2 instalado, agrega `C:\msys64\ucrt64\bin` y `C:\msys64\usr\bin` al PATH de la
> sesión antes de compilar.

### Instalar el conector de MySQL (una sola vez)

`DatabaseManager` se conecta a MySQL real usando el conector C de MariaDB (compatible con el
protocolo de MySQL 8):

```powershell
# Windows (MSYS2 ucrt64)
C:\msys64\usr\bin\bash.exe -lc "pacman -S --noconfirm mingw-w64-ucrt-x86_64-libmariadbclient mingw-w64-ucrt-x86_64-pkgconf"
```

```bash
# Linux (Debian/Ubuntu)
sudo apt install libmariadb-dev pkg-config
```

### Variables de entorno (conexión a MySQL)

Las mismas que usa `src/database/carga_concurrente.py`:

```powershell
$env:MYSQL_HOST = "127.0.0.1"        # opcional, por defecto 127.0.0.1
$env:MYSQL_PORT = "3306"             # opcional, por defecto 3306
$env:MYSQL_USER = "monitoreo_app"    # recomendado para la aplicación
$clave = Read-Host "Contraseña MySQL" -AsSecureString
$env:MYSQL_PASSWORD = [System.Net.NetworkCredential]::new("", $clave).Password
$env:MYSQL_DATABASE = "monitoreo_ambiental"  # opcional
```

Antes de correr la demo por primera vez, crea el esquema con una cuenta administradora y
después configura la cuenta de aplicación con permisos `SELECT` e `INSERT` sobre el esquema
(ver [src/database/README.md](../database/README.md)):

```powershell
mysql -u root -p < ..\database\schema.sql
```

### Compilar

```bash
cd src/cpp_ingestion
make            # compila la demo y las pruebas en bin/
make run-demo   # corre un lote finito (6 sensores x 50 lecturas) contra MySQL
make run-continuo  # modo continuo: genera lecturas simuladas y las persiste hasta Ctrl+C
make test       # corre las pruebas de concurrencia (no requieren MySQL)
make clean      # borra los binarios generados
```

`bin/demo` acepta argumentos opcionales: `bin/demo [num_sensores] [lecturas_por_sensor] [num_workers] [intervalo_ms]`.
Si `lecturas_por_sensor` es `0` (o se omite), corre en **modo continuo** hasta Ctrl+C,
imprimiendo un resumen cada 5 segundos — es el modo pensado para dejarlo corriendo mientras
se ve el dashboard (`src/dashboard/`) actualizarse con lecturas simuladas almacenadas en MySQL.

## Pruebas de concurrencia

- `tests/prueba_condicion_carrera.cpp`: reproduce exactamente el escenario de la sección 3.1
  del Documento de Justificación (un acumulador compartido incrementado por N hilos) y
  compara una versión **sin** mutex (pierde datos de forma medible) contra una versión
  **con** mutex (siempre exacta). Útil para sustentar oralmente por qué el mecanismo elegido
  es necesario y no opcional.
- `tests/prueba_cola_concurrente.cpp`: prueba de carga de la `ColaConcurrente` con 15
  productores y 5 consumidores y una capacidad pequeña (fuerza bloqueo en ambos sentidos),
  verificando que el total de ítems consumidos sea exactamente el total producido.
- `src/main.cpp` (la demo): al final informa lecturas guardadas, duplicados y errores de
  persistencia; el modo finito falla si alguna lectura no queda guardada o reconocida como
  duplicada.

## Límites y configuración de la demo

- Las lecturas sintéticas sirven para demostrar concurrencia; las mediciones físicas requieren
  un dispositivo y calibración externos. MQTT acepta dispositivos que cumplan el formato
  documentado en `src/api_fastapi/README.md`.
- La API calcula y muestra promedios móviles de 8 h/24 h; el registro de alertas actual se
  genera por superaciones puntuales.
- La carga de MySQL se ejecuta bajo demanda (`src/database/carga_concurrente.py`) contra una
  base autorizada; el informe distingue resultados ejecutados de pruebas disponibles.
