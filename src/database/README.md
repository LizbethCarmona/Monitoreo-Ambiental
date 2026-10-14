# Base de datos (`src/database`)

Esquema relacional MySQL 8 y pruebas de carga concurrente. Corresponde a las Semanas 3-4 del
cronograma ("esquema relacional/series temporales" y "persistencia concurrente y
transacciones").

## Contenido

- `schema.sql`: crea la base `monitoreo_ambiental` con cuatro tablas (`sensores`, `lecturas`,
  `umbrales`, `alertas`), índices temporales y los umbrales iniciales (ver fuentes normativas
  citadas dentro del archivo: NOM-025-SSA1-2021, NOM-010-STPS-2014, NOM-015-STPS-2001).
- `datos_prueba.sql`: procedimientos `generar_datos_prueba(sensores, lecturas)` y
  `limpiar_datos_prueba()` para pruebas de volumen/rendimiento.
- `carga_concurrente.py`: simula N sensores como N hilos escribiendo en paralelo (cada uno con
  su propia conexión), igual que lo hará `DatabaseManager` en C++, y verifica integridad
  (transacciones atómicas, rechazo de duplicados, reintentos ante deadlocks).
- `Base_de_datos_y_pruebas_de_carga.docx`: documento explicativo del equipo de base de datos.

## Cómo probarlo localmente

```sql
-- 1) Crear el esquema
SOURCE schema.sql;

-- 2) (Opcional) generar datos de volumen
CALL generar_datos_prueba(50, 2000);   -- 50 sensores x 2000 lecturas = 100,000 filas
```

```powershell
# 3) Prueba de carga concurrente real (requiere MySQL corriendo y el conector de Python)
pip install mysql-connector-python
$env:MYSQL_PASSWORD = "tu_clave"
python carga_concurrente.py --sensores 20 --lecturas 500
```

El script reporta lecturas guardadas, alertas generadas, duplicados rechazados (error 1062,
esperado por la restricción `UNIQUE KEY uq_sensor_momento`) y reintentos por deadlock (error
1213), y al final verifica que no existan alertas huérfanas.

## Conexión con el núcleo concurrente en C++ y la API

Esta base de datos ya está conectada de verdad a los otros dos componentes:

- `src/cpp_ingestion/` (`DatabaseManager`) inserta aquí las lecturas y alertas reales que
  genera el núcleo concurrente (ver `make run-continuo` en su README).
- `src/api_fastapi/` lee de aquí para `getEstadoClima()`/`getAlertas()`.

Los tres componentes se conectan con las mismas variables de entorno
(`MYSQL_HOST`/`MYSQL_PORT`/`MYSQL_USER`/`MYSQL_PASSWORD`/`MYSQL_DATABASE`).

`src/cpp_ingestion/include/Umbrales.hpp` replica manualmente los valores de la tabla
`umbrales` de este esquema. Si el equipo de base de datos cambia un umbral aquí, debe
actualizarse también ese archivo (pendiente: que `DatabaseManager` lea los umbrales
directamente de MySQL en vez de tenerlos hardcodeados).
