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

1. `SensorHiloProductor` simula N sensores (uno por `std::thread`) generando lecturas
   sintéticas y las empuja a una `ColaConcurrente` compartida.
2. `ColaConcurrente` es una *blocking queue* con `std::mutex` + 2 `std::condition_variable`:
   bloquea productores si está llena y consumidores si está vacía, sin *busy-waiting*.
3. `ThreadPoolConsumidor` lanza un pool de hilos que extraen de la cola, actualizan un
   acumulador de promedios compartido (protegido con mutex) y evalúan umbrales
   (`include/Umbrales.hpp`, sincronizados con `src/database/schema.sql`).
4. `DatabaseManager` persiste cada lectura (y su alerta, si aplica) como una única
   transacción real de MySQL (`START TRANSACTION` / `COMMIT` / `ROLLBACK`), usando el
   conector C de MariaDB (protocolo compatible con MySQL 8). Esto ya está conectado de
   verdad contra `src/database/schema.sql` (adelantado respecto al cronograma, que lo
   planeaba para la Semana 4).

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
$env:MYSQL_USER = "root"             # opcional, por defecto root
$env:MYSQL_PASSWORD = "tu_clave"     # obligatoria
$env:MYSQL_DATABASE = "monitoreo_ambiental"  # opcional
```

Antes de correr la demo por primera vez, crea el esquema real (ver
[src/database/README.md](../database/README.md)):

```powershell
mysql -u root -p < ..\database\schema.sql
```

### Compilar

```bash
cd src/cpp_ingestion
make            # compila la demo y las pruebas en bin/
make run-demo   # corre un lote finito (6 sensores x 50 lecturas) contra MySQL real
make run-continuo  # modo continuo: alimenta MySQL cada 3s hasta Ctrl+C ("tiempo real")
make test       # corre las pruebas de concurrencia (no requieren MySQL)
make clean      # borra los binarios generados
```

`bin/demo` acepta argumentos opcionales: `bin/demo [num_sensores] [lecturas_por_sensor] [num_workers] [intervalo_ms]`.
Si `lecturas_por_sensor` es `0` (o se omite), corre en **modo continuo** hasta Ctrl+C,
imprimiendo un resumen cada 5 segundos — es el modo pensado para dejarlo corriendo mientras
se ve el dashboard (`src/dashboard/`) actualizarse con datos reales.

## Pruebas de concurrencia

- `tests/prueba_condicion_carrera.cpp`: reproduce exactamente el escenario de la sección 3.1
  del Documento de Justificación (un acumulador compartido incrementado por N hilos) y
  compara una versión **sin** mutex (pierde datos de forma medible) contra una versión
  **con** mutex (siempre exacta). Útil para sustentar oralmente por qué el mecanismo elegido
  es necesario y no opcional.
- `tests/prueba_cola_concurrente.cpp`: prueba de carga de la `ColaConcurrente` con 15
  productores y 5 consumidores y una capacidad pequeña (fuerza bloqueo en ambos sentidos),
  verificando que el total de ítems consumidos sea exactamente el total producido.
- `src/main.cpp` (la demo): al final compara `lecturas generadas` vs `lecturas procesadas` vs
  `lecturas guardadas`; si no coinciden exactamente, es evidencia de una condición de carrera
  no resuelta.

## Pendiente (próximos sprints)

- Sprint 3 (Semanas 5-6): `SensorHiloProductor::recibirLecturasMQTT()` debe reemplazar la
  simulación por una suscripción real a un broker MQTT.
- Leer los umbrales directamente de la tabla `umbrales` en vez de tenerlos hardcodeados en
  `include/Umbrales.hpp` (hoy deben mantenerse sincronizados manualmente).
