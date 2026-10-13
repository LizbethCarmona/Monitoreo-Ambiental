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
   "transacción" protegida por mutex. **Nota:** por ahora escribe en archivos de bitácora
   (`lecturas.log`/`alertas.log`) en lugar de MySQL real; la integración con MySQL desde C++
   está planeada para la Semana 4 del cronograma. El esquema real ya existe en
   `src/database/schema.sql`.

## Compilar y correr

> **Windows:** el MinGW.org clásico no soporta `std::thread`. Se necesita un mingw-w64 (por
> ejemplo MSYS2 `ucrt64`) o compilar directamente en Linux/WSL, que es donde el equipo
> planea correr el sistema finalmente (ver pregunta abierta en el Documento de
> Justificación, sección final).
>
> Con MSYS2 instalado, agrega `C:\msys64\ucrt64\bin` y `C:\msys64\usr\bin` al PATH de la
> sesión antes de compilar.

```bash
cd src/cpp_ingestion
make            # compila la demo y las pruebas en bin/
make run-demo   # corre el pipeline completo (productores -> cola -> pool -> persistencia)
make test       # corre las pruebas de concurrencia
make clean      # borra los binarios y bitácoras generadas
```

También se puede compilar manualmente, por ejemplo:

```bash
g++ -std=c++17 -Iinclude -pthread -o bin/demo src/main.cpp src/SensorHiloProductor.cpp \
    src/ThreadPoolConsumidor.cpp src/DatabaseManager.cpp
./bin/demo 6 50 4   # 6 sensores, 50 lecturas c/u, pool de 4 hilos
```

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

- Sprint 2 (Semana 4): reemplazar `DatabaseManager` por un cliente real de MySQL
  (`libmysqlclient` o MySQL Connector/C++) usando transacciones reales
  (`START TRANSACTION` / `COMMIT`), conforme a `src/database/schema.sql`.
- Sprint 3 (Semanas 5-6): `SensorHiloProductor::recibirLecturasMQTT()` debe reemplazar la
  simulación por una suscripción real a un broker MQTT.
