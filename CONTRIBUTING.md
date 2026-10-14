# Guía de contribución

Convenciones acordadas por el equipo para trabajar de forma ordenada durante las 9 semanas
del proyecto.

## Ramas

- **`main`**: solo el código oficial/estable. Se actualiza al cierre de cada sprint, cuando
  una entrega ya fue validada.
- **`develop`**: aquí se van subiendo los avances de cada sprint antes de llegar a `main`.
- **Ramas personales**: cada integrante trabaja en su propia rama (por ejemplo
  `feature/nucleo-concurrente-axel`, `feature/bd-eduardo`, `feature/api-samael`) y la
  fusiona a `develop` vía Pull Request cuando su parte está lista y probada.

Flujo sugerido:

```
feature/mi-rama  --PR-->  develop  --(cierre de sprint)-->  main
```

## Mensajes de commit

Todos los commits deben empezar con una etiqueta corta que indique qué tipo de cambio es,
para poder leer el historial de Git y saber rápido qué hizo cada quien:

| Prefijo | Cuándo usarlo |
|---|---|
| `feat:` | Se agrega una función/funcionalidad nueva |
| `fix:` | Se corrige un error o bug |
| `docs:` | Se sube o actualiza documentación/reportes |
| `db:` | Cambios en scripts de MySQL / esquema / datos de prueba |

Ejemplos:

```
feat: implementar ColaConcurrente con mutex y condition_variable
fix: corregir fuga de hilos en ThreadPoolConsumidor al cerrar la cola
docs: agregar diagrama de arquitectura en docs/arquitectura.md
db: agregar indice temporal a la tabla lecturas
```

## Estructura de carpetas

- `src/cpp_ingestion/`: todo lo de C++ (núcleo concurrente, hilos, colas).
- `src/api_fastapi/`: todo lo de la API/servicio web (FastAPI).
- `src/database/`: scripts de MySQL (esquema, datos de prueba, pruebas de carga).
- `docs/`: reportes, UML, JSON de métricas y cronograma.

## Revisión cruzada (Definition of Done)

Antes de fusionar a `develop`, un compañero **de un rol distinto** debe revisar el cambio
(por ejemplo, un cambio en la API lo revisa alguien del núcleo concurrente). Ver la sección
8 del [Documento de Justificación](docs/justificacion/Documento_Justificacion_Equipo_PC.pdf)
para la Definition of Done completa (pruebas de concurrencia, transaccionalidad, etc.).

## Uso de IA

El profesor autorizó usar IA como apoyo, con dos condiciones:

1. Debe citarse (indicar en el commit/PR o en el documento qué se generó con ayuda de IA).
2. Solo puede usarse con el correo institucional (`@my.uvm.edu.mx`), con Gemini.
