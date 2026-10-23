# Dashboard web (`src/dashboard`)

Interfaz visual del proyecto: tarjeta ambiental, observaciones por hora y panel de alertas,
con datos de MySQL consultados por API. Las fuentes admitidas son simulación C++ o MQTT.
Replica el mockup de referencia acordado por el equipo. Corresponde al
componente "Dashboard" del diagrama de arquitectura
([docs/arquitectura.md](../../docs/arquitectura.md)) y adelanta el Sprint 4 (Semana 7).

## Cómo verlo

Se sirve automáticamente junto con la API (no es necesario un servidor aparte):

```powershell
Set-Location src\api_fastapi
..\..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

En Linux/macOS, con el entorno virtual activado:

```bash
cd src/api_fastapi
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Abre `http://127.0.0.1:8000/dashboard/` en el navegador.

Antes de iniciar Uvicorn, configura en esa misma terminal las variables `MYSQL_HOST`,
`MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD` y `MYSQL_DATABASE` que correspondan a tu MySQL.
PowerShell no las comparte automáticamente con otras terminales. Si Uvicorn ya está activo
en una terminal sin esas variables, detenlo con `Ctrl+C` y reinícialo en la terminal configurada.

El acceso local de desarrollo no requiere iniciar sesión por defecto. Para que varias personas
entren desde equipos distintos por Internet, se debe desplegar FastAPI con cuentas individuales
y HTTPS mediante Docker Compose y Caddy. Eso requiere un servidor público, un dominio y una
instancia MySQL accesible desde el servidor. Consulta la
[guía de despliegue multiusuario](../api_fastapi/README.md#despliegue-multiusuario-en-internet).

## Cómo funciona

- HTML/CSS/JS plano (sin frameworks ni build step) para que cualquiera del equipo lo pueda
  editar sin instalar nada extra.
- El dashboard no es una aplicación o contenedor independiente: FastAPI sirve estos archivos
  estáticos en `/dashboard/`. No requiere Node.js. MySQL debe estar disponible para que la API
  obtenga los datos. Para la demo local Docker es opcional, salvo que se use MQTT con Mosquitto;
  para el despliegue multiusuario, Compose ejecuta FastAPI y Caddy delante de MySQL externo.
- Al abrir el dashboard, `app.js` carga el estado inicial y las alertas mediante REST, y se
  conecta a `WS /ws/dashboard`. WebSocket mantiene abierto el canal navegador–API: envía al
  cliente un snapshot JSON inicial y la API comparte una consulta MySQL para difundir el estado
  y las alertas aproximadamente cada 2 s a los clientes conectados. El cliente manda `ping`
  cada 20 s y recibe `pong`. WebSocket solo comunica actualizaciones del dashboard; no recibe
  los mensajes MQTT ni escribe lecturas en MySQL. Si el canal se desconecta, REST consulta cada
  cinco segundos mientras el cliente intenta reconectar. El historial se solicita por
  `/alertas/historial`.
- “Alertas activas” significa alertas que aún no se marcaron como atendidas; son eventos
  puntuales guardados, no una predicción ni una evaluación continua. El panel muestra hasta
  20 recientes y permite consultar hasta 100 del historial.
- Los colores de los puntos (verde/amarillo/rojo) se calculan a partir de los campos
  `*_nivel` que ya vienen en la respuesta de la API (`normal` | `advertencia` | `critico`),
  el mismo vocabulario que usa `ThreadPoolConsumidor::evaluarUmbrales` en el núcleo
  concurrente de C++.
- La tabla de las últimas 24 h muestra por fila una hora con lecturas, el promedio de PM2.5
  (`µg/m³`), su clasificación y la temperatura promedio (`°C`). El color solo corresponde a
  la clasificación de PM2.5, basada en los límites puntuales provisionales del prototipo; las
  horas se presentan en UTC.
- En pantallas estrechas, la tabla se transforma en filas tipo ficha con el nombre de cada
  dato visible, para conservar legibles sus valores y unidades.
- La tarjeta de alertas activas se mantiene como un panel independiente junto a la tarjeta
  ambiental. Su lista tiene desplazamiento propio cuando hay muchas alertas; el enlace permite
  cambiar entre alertas activas (hasta 20 recientes) y el historial (hasta 100 recientes).
  En pantallas estrechas, las tarjetas se apilan y la lista conserva su desplazamiento dentro
  del borde.

## Alcance y límites

- El rótulo de ciudad se configura con `CIUDAD_NOMBRE`; el esquema actual no asocia una
  ubicación a cada sensor.
- La temperatura presentada es la lectura más reciente almacenada, no un pronóstico
  meteorológico. La etiqueta «Fuente» identifica el sensor de esa última lectura; con el
  simulador, los valores son sintéticos y no provienen de hardware físico. El origen de los
  mensajes puede ser el simulador o un publicador MQTT configurado.
