# Base de datos (`src/database`)

Esquema relacional MySQL 8 y pruebas de carga concurrente. Corresponde a las Semanas 3-4 del
cronograma ("esquema relacional/series temporales" y "persistencia concurrente y
transacciones").

Para instalar MySQL Server, crear la base sin MySQL Workbench y ejecutar el proyecto desde
cero en Windows, consulta el [manual de usuario](../../docs/manual_usuario.md).

## Contenido

- `schema.sql`: crea la base `monitoreo_ambiental` con cuatro tablas (`sensores`, `lecturas`,
  `umbrales`, `alertas`), índices temporales y referencias de umbrales con sus limitaciones
  (NOM-025-SSA1-2021, NOM-010-STPS-2014, NOM-015-STPS-2001).
- `actualizar_umbrales_verificados.sql`: ajuste no destructivo de los valores/fuentes de
  umbral en una base existente; requiere ejecución explícita con una cuenta autorizada.
- `datos_prueba.sql`: procedimientos `generar_datos_prueba(sensores, lecturas)` y
  `limpiar_datos_prueba()` para pruebas de volumen/rendimiento.
- `carga_concurrente.py`: simula N sensores como N hilos escribiendo en paralelo (cada uno con
  su propia conexión), igual que lo hará `DatabaseManager` en C++, y verifica integridad
  (transacciones atómicas, rechazo de duplicados, reintentos ante deadlocks).
- `Base_de_datos_y_pruebas_de_carga.docx`: documento explicativo del equipo de base de datos.

## Qué guarda MySQL y qué no

MySQL Server es el almacén persistente compartido por los productores C++ y la API FastAPI.
`sensores` es el catálogo; `lecturas` guarda los valores recibidos y sus marcas de tiempo;
`umbrales` contiene los valores de comparación; `alertas` guarda eventos ligados a una lectura.
La integridad se protege con claves y transacciones. La API calcula los promedios horarios y
móviles al consultar; no guarda esos promedios como lecturas ni como alertas.

MySQL es un servicio aparte: el `docker compose` de `src/api_fastapi` ejecuta solo el broker
Mosquitto para MQTT. No crea, aloja ni limpia la base de datos. Al detener Docker Compose,
MySQL conserva sus registros; para eliminar lecturas y alertas sigue el procedimiento de
limpieza de más abajo.

Al visualizar estos datos, FastAPI consulta MySQL y envía el estado y las alertas al navegador
por la conexión WebSocket del dashboard, aproximadamente cada 2 s. WebSocket es transporte
en vivo de salida para la interfaz; no es una tabla, no persiste datos ni reemplaza MySQL.
Las consultas REST cargan el estado inicial y el historial, y sirven como respaldo temporal
si WebSocket se desconecta.

## Cómo probarlo localmente

```sql
-- 1) Crear el esquema
SOURCE schema.sql;

-- 2) (Opcional) generar datos de volumen
CALL generar_datos_prueba(50, 2000);   -- 50 sensores x 2000 lecturas = 100,000 filas
```

```powershell
# Desde la raíz del repositorio
Set-Location src\database
..\..\.venv\Scripts\python.exe -m unittest discover -s tests -v

# 3) Desde la raíz del repositorio: configuración local sin mostrar la contraseña
$env:MYSQL_HOST = "127.0.0.1"
$env:MYSQL_PORT = "3306"
$env:MYSQL_USER = "monitoreo_app"
$clave = Read-Host "Contraseña MySQL" -AsSecureString
$env:MYSQL_PASSWORD = [System.Net.NetworkCredential]::new("", $clave).Password
$env:MYSQL_DATABASE = "monitoreo_ambiental"

# Ejecuta la prueba desde la raíz; usa las variables MYSQL_* anteriores
Set-Location ..\..
.\.venv\Scripts\python.exe src\database\carga_concurrente.py --sensores 20 --lecturas 500
```

El script reporta lecturas guardadas, alertas generadas, duplicados rechazados (error 1062,
esperado por la restricción `UNIQUE KEY uq_sensor_momento`) y reintentos por deadlock (error
1213), y al final verifica que no existan alertas huérfanas.

La ejecución del 14-oct-2026 con 20 sensores x 500 intentos y duplicados 0.05 pasó:
9,500 lecturas y 2,627 alertas verificadas, 500 duplicados esperados, cero huérfanas y cero
errores inesperados. El detalle reproducible está en [docs/informe_pruebas.md](../../docs/informe_pruebas.md).
Los resultados anteriores son evidencia histórica. El 15-oct-2026, después de esa prueba, se
limpió la instancia local de demostración: se eliminaron 15,040 alertas y 32,344 lecturas y
se verificaron ambas tablas en cero. Las tablas, sensores y umbrales se conservaron. Las nuevas
lecturas y alertas volverán a aparecer en cuanto se ejecute un productor.

### Dejar vacío el historial del dashboard

Detén primero el simulador MQTT y cualquier productor C++ para que no inserten datos durante la
limpieza. En MySQL Workbench o en el cliente `mysql`, comprueba que estás en
`monitoreo_ambiental` y revisa los conteos antes de borrar:

Ejecuta los `DELETE` con una cuenta administradora o con una cuenta autorizada explícitamente
para borrar filas en este esquema. La cuenta de aplicación de la API solo requiere `SELECT` e
`INSERT`; no le concedas `DELETE` solo para limpiar el historial.

```sql
USE monitoreo_ambiental;
SELECT COUNT(*) AS lecturas_antes FROM lecturas;
SELECT COUNT(*) AS alertas_antes FROM alertas;
```

Si confirmas que quieres borrar **todas** las lecturas y alertas de esa base, borra primero las
alertas (dependen de las lecturas) y después las lecturas:

```sql
START TRANSACTION;
DELETE FROM alertas WHERE alerta_id > 0;
DELETE FROM lecturas WHERE lectura_id > 0;
SELECT COUNT(*) AS lecturas_despues FROM lecturas;
SELECT COUNT(*) AS alertas_despues FROM alertas;
```

Confirma con `COMMIT;` únicamente si las dos cantidades son cero y estás seguro de que limpiaste
la base correcta. Si algo no coincide, ejecuta `ROLLBACK;` en vez de `COMMIT;`. Este
procedimiento conserva las tablas, sensores y umbrales. Eliminar filas no necesariamente reduce
de inmediato el tamaño físico de los archivos de MySQL; ese espacio queda disponible para
reutilización. El historial volverá a llenarse cuando se inicie un simulador.

Para una base existente, `schema.sql` no sobrescribe filas de umbral porque usa `INSERT IGNORE`.
Revisa `actualizar_umbrales_verificados.sql` y ejecútalo explícitamente en la base autorizada
si deseas aplicar el valor PM2.5 fase Año 5 (25 µg/m³) y las fuentes/caveats verificados.
El script no borra lecturas ni alertas.

## Conexión con el núcleo concurrente en C++ y la API

Esta base de datos ya está conectada de verdad a los otros dos componentes:

- `src/cpp_ingestion/` (`DatabaseManager`) inserta aquí las lecturas simuladas y alertas que
  genera el núcleo concurrente (ver `make run-continuo` en su README).
- `src/api_fastapi/` lee de aquí para `getEstadoClima()`/`getAlertas()`.

Los tres componentes admiten las variables de entorno
(`MYSQL_HOST`/`MYSQL_PORT`/`MYSQL_USER`/`MYSQL_PASSWORD`/`MYSQL_DATABASE`). En el script de
carga, las opciones de conexión también pueden pasarse explícitamente por CLI; la contraseña
se toma de `MYSQL_PASSWORD`.

El núcleo C++ y la API leen los umbrales de la tabla `umbrales`, respetando el campo
`aplica_a` para diferenciar lecturas puntuales de promedios móviles. El consumidor C++ solo
evalúa alertas puntuales; la API calcula los promedios de 8 h y 24 h, pero todavía no persiste
alertas basadas en esos promedios.

## Alcance de las referencias de umbral

- PM2.5: NOM-025-SSA1-2021, Tabla 1, contiene valores graduales de 41, 33 y 25 µg/m³ para
  promedio de 24 h (Año 1, Año 3 y Año 5). El esquema usa 25 como referencia de fase Año 5
  al 14 de octubre de 2026. Los niveles instantáneos 35/75 µg/m³ son criterios del prototipo,
  no niveles de alerta establecidos por esa NOM.
- CO₂: NOM-010-STPS-2014, Apéndice I, Tabla I.1 (PDF p. 53), contiene VLE-PPT de 5,000 ppm
  y VLE-CT de 30,000 ppm. La definición 4.29 establece el nivel de acción como la mitad del
  VLE-PPT (2,500 ppm). Son referencias de exposición ocupacional; el VLE-CT no debe tratarse
  como límite de una lectura instantánea, y estos valores no certifican mediciones ambientales.
- Temperatura: NOM-015-STPS-2001 aplica un índice ITGBH, carga laboral y regímenes de
  exposición/recuperación. El prototipo solo mide temperatura del aire; sus criterios 30/32.2
  °C son heurísticos, no evaluación de estrés térmico conforme a la NOM.

Las fuentes y notas también están en `schema.sql`. El PDF STPS denominado `NOM-010.pdf`
corresponde a NOM-010-STPS-1999, por lo que no se usa para verificar la edición 2014.
Fuentes de la edición 2014: [PDF de gob.mx](https://www.gob.mx/cms/uploads/attachment/file/680155/NOM-010-STPS-2014.pdf)
y [publicación DOF](https://dof.gob.mx/normasOficiales/5359/stps2a11_C/stps2a11_C.html).
