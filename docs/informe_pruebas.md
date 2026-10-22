# Informe de verificación técnica

## Alcance verificado

La demostración contiene dos fuentes de lectura (simulador concurrente C++ y entrada MQTT),
persistencia MySQL, API REST, WebSocket compartido y dashboard. WebSocket mantiene el canal
navegador–API y difunde snapshots JSON de estado y alertas obtenidos de MySQL aproximadamente
cada 2 s; no es una ruta de ingesta ni de persistencia. REST carga inicialmente el dashboard,
sirve el historial y actúa como respaldo temporal durante una reconexión. La fuente de los
valores se identifica como simulada o externa; el prototipo no consulta un servicio meteorológico.

## Pruebas reproducibles

| Área | Prueba | Verificación |
|---|---|---|
| Cola concurrente | `make test` en `src/cpp_ingestion` | Los productores y consumidores drenan exactamente los elementos encolados; la prueba incluye 30 000 elementos. |
| Condición de carrera | `prueba_condicion_carrera` | La variante sin mutex pierde incrementos y la protegida llega al total esperado. |
| Clasificación API | `python -m unittest discover -s tests -p "test_*.py" -v` | Mantiene separados `lectura`, `promedio_8h` y `promedio_24h`; comprueba valores ausentes e historial. Instalar `requirements-dev.txt`. |
| WebSocket | Suite de API | Comprueba el snapshot JSON inicial de estado y alertas, la difusión a dos clientes simultáneos y el latido `ping`/`pong`. |
| MQTT | `test_mqtt_broker.py` | Con `MQTT_TEST_BROKER=127.0.0.1`, publica contra Mosquitto real, confirma la recepción QoS 1 y comprueba persistencia simulada por mock. |
| Validación y reintento MQTT | Suite de API | Rechaza topic/payload/fecha inválidos; no confirma el mensaje ante fallo MySQL. |
| Configuración de carga SQL | `src/database/tests/test_carga_concurrente.py` | Comprueba que host, puerto, usuario y esquema predeterminados se lean desde `MYSQL_*`. |
| Persistencia MySQL concurrente | `python src/database/carga_concurrente.py --sensores 20 --lecturas 500 --duplicados 0.05` | Ejecutada el 14-oct-2026: 10 000 intentos, 9 500 guardados, 500 duplicados esperados; filas y alertas coinciden, sin huérfanas. |

## Resultados obtenidos durante la finalización

- C++: compilación con MSYS2 UCRT64; prueba de carrera corregida, acumulador seguro de
  400 000 incrementos, cola con 15 productores y 5 consumidores, 30 000 elementos consumidos.
- API/MQTT/WebSocket: 13 pruebas de unidad/integración aprobadas al volver a ejecutar la suite
  con Mosquitto local en `127.0.0.1:1883`. La prueba de broker sustituye el guardado MySQL por
  un mock; las transacciones tienen pruebas unitarias específicas.
- C++: `make test` recompiló con MSYS2 UCRT64 y pasó ambas pruebas: la versión con mutex llegó
  a 400 000 incrementos, y la cola consumió los 30 000 elementos producidos.
- Configuración y carga MySQL: pasó la prueba unitaria del mapeo desde `MYSQL_*`. El 14-oct-2026
  se ejecutó en MySQL local la carga de 20 sensores/hilos x 500 intentos, duplicados 0.05:
  9,500 lecturas guardadas, 2,627 alertas, 500 duplicados rechazados (esperados), 0 reintentos
  por deadlock, 0 errores inesperados, 7.09 s y 1,340 lecturas guardadas/s. La verificación
  final encontró 9,500/9,500 lecturas, 2,627/2,627 alertas y 0 alertas huérfanas:
  `RESULTADO: OK, sin corrupción`. Evidencia: salida de terminal compartida por el usuario.
- Limpieza de la instancia local (15-oct-2026): después de conservar la evidencia de carga,
  el usuario borró y confirmó con `COMMIT` 15,040 filas de `alertas` y 32,344 filas de
  `lecturas`; las consultas posteriores mostraron ambas tablas con cero filas. Se conserva
  esta prueba como resultado histórico; las cifras de carga no describen el contenido actual
  de la base local. La limpieza no eliminó tablas, sensores ni umbrales y no afecta el
  funcionamiento del proyecto. Cuando se detienen los productores y la API, el historial del
  dashboard permanece vacío hasta que se guarden lecturas nuevas.
- Python: la suite pasa; el cliente de pruebas emite una advertencia de obsolescencia de
  `starlette.testclient` con `httpx` (sin fallos). La reejecución del 14-oct-2026 pasó 12
  pruebas y omitió la prueba del broker real porque no se configuró `MQTT_TEST_BROKER`; la
  ejecución previa con Mosquitto local tuvo las 13 pruebas aprobadas. Pylance no reporta
  errores; quedan advertencias de variables/parámetros de callbacks no utilizados en
  `ingestion.py`.
- Verificación manual local (Windows, 13 de octubre de 2026): `/salud` respondió `ok` con
  MySQL conectado y MQTT habilitado/conectado. El simulador publicó lecturas MQTT para tres
  sensores; el usuario confirmó que el dashboard se actualizó y que `/estado-clima` devolvió
  lecturas. Esto verifica el recorrido funcional local
  simulador → broker MQTT → API → MySQL → dashboard usando datos sintéticos.
- La carga ejercita escritura concurrente de lecturas y alertas, rechazo de duplicados e
  integridad referencial en la base local. Es una prueba funcional de carga, no una medición
  de capacidad máxima, disponibilidad sostenida ni rendimiento de hardware de producción.

## Revisión de umbrales y fuentes normativas

- **PM2.5:** NOM-025-SSA1-2021, §4.1, Tabla 1, establece valores graduales de 41, 33 y
  25 µg/m³ para el promedio de 24 horas (Año 1, Año 3 y Año 5); 41 no es un límite fijo
  permanente. La referencia del prototipo se ajustó a la fase Año 5 (25 µg/m³) para el
  estado del proyecto al 14-oct-2026. La NOM no define los niveles instantáneos 35/75 usados
  para la demostración. Fuente: [DOF, NOM-025-SSA1-2021](https://www.dof.gob.mx/nota_detalle.php?codigo=5633855&fecha=27/10/2021).
- **CO₂:** se verificó en NOM-010-STPS-2014, §4.29, que el nivel de acción equivale a la mitad
  del VLE-PPT; Apéndice I, Tabla I.1 (PDF p. 53), lista CO₂ con VLE-PPT 5,000 ppm y VLE-CT
  30,000 ppm. El nivel de acción de 2,500 ppm es ocupacional. El VLE-CT aplica hasta 15 min,
  por lo que 30,000 ppm no valida una alerta por lectura instantánea del prototipo. La norma
  regula exposición en centros de trabajo, no calidad de aire exterior. Fuentes:
  [PDF oficial gob.mx](https://www.gob.mx/cms/uploads/attachment/file/680155/NOM-010-STPS-2014.pdf)
  y [publicación DOF](https://dof.gob.mx/normasOficiales/5359/stps2a11_C/stps2a11_C.html).
- **Temperatura:** NOM-015-STPS-2001, §8.1, Tabla 1 (PDF p. 5), define condiciones ITGBH
  según intensidad de trabajo y exposición/recuperación; §7.3.5 regula condiciones de
  exposición momentánea por arriba de 32.2 °C ITGBH. No son umbrales universales de temperatura
  del aire. Los valores 30/32.2 del sistema se etiquetan como heurísticos provisionales.
  Fuente: [STPS, NOM-015-STPS-2001](https://www.stps.gob.mx/bp/secciones/dgsst/normatividad/normas/Nom-015.pdf).
- **Límite de aplicación:** todos son referencias o reglas informativas en este prototipo.
  Las lecturas son sintéticas; no equivalen a mediciones certificadas ni a evaluación
  ocupacional.

## Límites de la evidencia y del producto

- La prueba automatizada del broker sustituye el almacenamiento MySQL por un mock. La
  verificación manual posterior conectó MQTT con la instancia MySQL local. De forma separada,
  la prueba concurrente SQL documentada arriba sí se ejecutó contra MySQL local; ninguna de
  estas verificaciones constituye por sí sola una prueba de disponibilidad o capacidad de
  producción.
- La integración de sensores físicos y su calibración están fuera del alcance del proyecto.
  Las pruebas validan el flujo con datos sintéticos; no evalúan la exactitud de instrumentos.
- La instancia local de demostración quedó actualmente sin lecturas ni alertas después de la
  limpieza confirmada; para revisar el dashboard vacío, mantener detenidos el simulador MQTT
  y el productor C++.
- La presentación calendarizada solo puede marcarse realizada en su fecha. El guion y los
  comandos reproducibles quedan preparados por el equipo.
