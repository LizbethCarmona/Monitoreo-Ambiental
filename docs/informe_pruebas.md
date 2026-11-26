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
| API, umbrales y fechas | `python -m unittest discover -s tests -p "test_*.py" -v` | Mantiene separados `lectura`, `promedio_8h` y `promedio_24h`; comprueba valores ausentes, historial, normalización UTC y rechazo de timestamps futuros. Instalar `requirements-dev.txt`. |
| WebSocket | Suite de API | Comprueba el snapshot JSON inicial de estado y alertas, la difusión a dos clientes simultáneos y el latido `ping`/`pong`. |
| MQTT | `test_mqtt_broker.py` | Con `MQTT_TEST_BROKER=127.0.0.1`, publica contra Mosquitto real, confirma la recepción QoS 1 y comprueba persistencia simulada por mock. |
| Validación y reintento MQTT | Suite de API | Rechaza topic/payload/fecha inválidos, incluido timestamp futuro; no confirma el mensaje ante fallo MySQL. |
| Configuración de carga SQL | `src/database/tests/test_carga_concurrente.py` | Comprueba que host, puerto, usuario y esquema predeterminados se lean desde `MYSQL_*`. |
| Persistencia MySQL concurrente | `python src/database/carga_concurrente.py --sensores 20 --lecturas 500 --duplicados 0.05` | Ejecutada el 14-oct-2026: 10 000 intentos, 9 500 guardados, 500 duplicados esperados; filas y alertas coinciden, sin huérfanas. |

## Resultados obtenidos durante la finalización

- API/MQTT/WebSocket: 13 pruebas de unidad/integración aprobadas en una ejecución anterior
  con Mosquitto local en `127.0.0.1:1883`. La prueba de broker sustituye el guardado MySQL por
  un mock; las transacciones tienen pruebas unitarias específicas.
- Carga MySQL histórica: el 14-oct-2026 se ejecutó en la base local la carga de 20 sensores/hilos
  x 500 intentos, duplicados 0.05:
  9,500 lecturas guardadas, 2,627 alertas, 500 duplicados rechazados (esperados), 0 reintentos
  por deadlock, 0 errores inesperados, 7.09 s y 1,340 lecturas guardadas/s. La verificación
  final encontró 9,500/9,500 lecturas, 2,627/2,627 alertas y 0 alertas huérfanas:
  `RESULTADO: OK, sin corrupción`. Evidencia: salida de terminal compartida por el usuario.
- Limpieza de la instancia local (15-oct-2026): después de conservar la evidencia de carga,
  el usuario borró y confirmó con `COMMIT` 15,040 filas de `alertas` y 32,344 filas de
  `lecturas`; las consultas posteriores mostraron ambas tablas con cero filas. Se conserva
  esta limpieza como evidencia histórica; no describe el contenido actual de la base, que se
  vuelve a poblar cuando se ejecuta un productor. La limpieza no eliminó tablas, sensores ni
  umbrales.
- Python: `requirements-dev.txt` usa `httpx2`; la suite actual no reportó la advertencia de
  deprecación de `starlette.testclient`. Ejecuciones anteriores omitieron la prueba de broker
  real cuando no se configuró `MQTT_TEST_BROKER`. Pylance no reportó diagnósticos en
  `ingestion.py` ni `simulador_mqtt.py` tras aclarar el descarte de parámetros callback
  requeridos por Paho.
- Verificación manual local (Windows, 13 de octubre de 2026): `/salud` respondió `ok` con
  MySQL conectado y MQTT habilitado/conectado. El simulador publicó lecturas MQTT para tres
  sensores; el usuario confirmó que el dashboard se actualizó y que `/estado-clima` devolvió
  lecturas. Esto verifica el recorrido funcional local
  simulador → broker MQTT → API → MySQL → dashboard usando datos sintéticos.
- Verificación multiusuario privada: se ejecutó el stack de Compose con autenticación de
  producción, cookies `Secure` y MySQL persistente; Tailscale Serve entregó HTTPS solo al
  tailnet autorizado. Se confirmó la ruta de login con HTTP 200, una ruta de datos anónima con
  HTTP 401 y dos sesiones independientes, donde cerrar sesión en una no invalidó la otra.
  La URL se forma como `https://<TAILNET_HOSTNAME>/dashboard/`; requiere Tailscale conectado y el
  anfitrión encendido. No es un despliegue público y no se validó acceso desde Internet.
- En la ejecución de cierre del 6-nov-2026, las 24 pruebas de API pasaron al configurar
  `MQTT_TEST_BROKER=127.0.0.1` y usar el Mosquitto local; también pasó 1 prueba de configuración
  de base de datos. Sin esa variable, la prueba del broker se omite.
- Revalidación previa del 25-nov-2026: las 26 pruebas API pasaron, incluida la integración con el
  Mosquitto real (`MQTT_TEST_BROKER=127.0.0.1`); la prueba de configuración SQL pasó (1/1).
  Las dos pruebas C++ pasaron con MSYS2 UCRT64: 400 000 incrementos protegidos y 30 000
  elementos consumidos sin pérdida ni duplicación. Compose pasó `config --quiet`. Se reemplazó
  `httpx` por `httpx2` en dependencias de desarrollo y la suite ya no emite la advertencia de
  deprecación de `starlette.testclient`.
- Revalidación final del 25-nov-2026: las 27 pruebas API pasaron con Mosquitto real,
  incluida la prueba de cruce de medianoche UTC/CDMX. El dashboard local mostró el 25-nov para
  un timestamp del 26-nov UTC; las horas del historial permanecieron en UTC.
- Verificación operativa posterior al reinicio (25-nov-2026): `/healthz` respondió `ok` y
  `/salud` informó MySQL y MQTT conectados. La API local del dashboard en `127.0.0.1:8001`
  devolvió el estado esperado; el contador de errores del proceso nuevo quedó en cero y
  `ultimo_error` vacío. Este contador es volátil y se reinicia al arrancar el proceso, por lo
  que no representa errores históricos. El API Compose usa `monitoreo-api-compose` para evitar
  colisiones de identificador MQTT con una instancia local.
- La carga ejercita escritura concurrente de lecturas y alertas, rechazo de duplicados e
  integridad referencial en la base local. Es una prueba funcional de carga, no una medición
  de capacidad máxima, disponibilidad sostenida ni rendimiento de hardware de producción.

## Revisión de umbrales y fuentes normativas

- **PM2.5:** NOM-025-SSA1-2021, §4.1, Tabla 1, establece valores graduales de 41, 33 y
  25 µg/m³ para el promedio de 24 horas (Año 1, Año 3 y Año 5); 41 no es un límite fijo
  permanente. El segundo transitorio establece que la aplicación de los incisos 4.2.5 y 4.2.6
  inicia en el año calendario posterior a la publicación; por ello, el calendario 2026
  corresponde a la fase Año 5 (25 µg/m³). La Tabla 1 también establece 10 µg/m³ para el
  promedio anual. La NOM define el promedio diario en un periodo
  continuo de 24 horas desde las 00:00, exige al menos 75 % de concentraciones horarias válidas
  (18 de 24) para el promedio automático o equivalente y evalúa el criterio de 24 h mediante
  el percentil 99 anual; también requiere calcular el promedio anual. La API usa un promedio
  móvil de las filas disponibles de las últimas 24 h, mezcla sensores, no valida cobertura ni
  calcula el percentil o el promedio anual; mostrar 25 µg/m³ es una referencia orientativa, no
  una evaluación de cumplimiento. La NOM tampoco define los niveles instantáneos 35/75 usados
  para la demostración. Fuentes: [DOF, NOM-025-SSA1-2021](https://www.dof.gob.mx/nota_detalle.php?codigo=5633855&fecha=27/10/2021)
  y [texto oficial SIDOF](https://sidof.segob.gob.mx/notas/docFuente/5633855).
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
- El 6-nov-2026 una consulta de solo lectura mientras el simulador estaba activo encontró
  9,834 lecturas, 5,337 alertas y 3 sensores. Es una observación puntual: los conteos cambian
  conforme se generan datos sintéticos.
- La presentación calendarizada solo puede marcarse realizada en su fecha. El guion y los
  comandos reproducibles quedan preparados por el equipo.
