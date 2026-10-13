# Simulador IoT (prototipo inicial — Semana 1, HU01)

Este prototipo es el primer intento del equipo de red/servicios (Axel) para la Historia de
Usuario 1 ("recibir lecturas de múltiples sensores simultáneamente usando hilos"). Se
conserva aquí como referencia histórica del Sprint 1, pero **el núcleo concurrente oficial
del proyecto vive en `src/cpp_ingestion/` (carpeta padre)**, no aquí.

## Qué hace

- `scripts/sim_temp.lua` y `scripts/sim_hum.lua`: dos scripts Lua independientes que escriben
  continuamente un valor aleatorio (temperatura y humedad) a `temperature.txt` y
  `humidity.txt` respectivamente.
- `src/main.cpp`: lanza dos `std::thread` (uno por archivo) que leen esos archivos en bucle y
  actualizan dos variables globales (`currTemp`, `currHum`) que el hilo principal imprime cada
  segundo.

## Por qué no es la versión final

Este prototipo sirvió para validar que se podían lanzar hilos lectores en C++, pero tiene
limitaciones que el núcleo concurrente oficial (`src/cpp_ingestion/include` y `src/`) corrige:

1. **No hay cola compartida ni mecanismo productor-consumidor real**: cada hilo lector escribe
   directamente a una variable global (`currTemp`/`currHum`) sin mutex. Dos hilos (el lector y
   el hilo principal que imprime) acceden a esas variables al mismo tiempo sin sincronización,
   lo que es en sí mismo una condición de carrera de dato (*data race* no definida por el
   estándar de C++).
2. **No hay pool de hilos ni cálculo de agregados/umbrales.**
3. **No hay persistencia**: solo imprime en consola.
4. La comunicación por archivo de texto (`.lua` escribe, `.cpp` lee) no escala a N sensores y
   no corresponde al modelo productor-consumidor con `ColaConcurrente` definido en el UML.

Se mantiene el código tal cual lo entregó el equipo, sin modificarlo, para no perder el
historial de la Semana 1. El Makefile de `src/cpp_ingestion/` **no** compila esta carpeta.
