# Manual de usuario: instalación y ejecución desde cero

Esta guía está pensada para una persona que recibe el proyecto por primera vez. Explica qué
instalar, cómo preparar la base de datos sin MySQL Workbench, cómo iniciar la demostración y
qué hacer si algo no funciona. Los comandos son para **Windows 10/11 y PowerShell**.

> **Alcance:** el proyecto de clase se demuestra con datos sintéticos generados por simuladores.
> No requiere ni contempla instalar sensores físicos. El broker MQTT de desarrollo permite
> conexiones anónimas únicamente en el equipo local; no lo expongas a Internet ni a una red.
> Docker Compose también contiene un despliegue separado para FastAPI y Caddy con login y HTTPS;
> MySQL sigue siendo externo. Si quieres compartir el dashboard desde varios equipos por
> Internet, consulta la [guía de despliegue multiusuario](../src/api_fastapi/README.md#despliegue-multiusuario-en-internet).
> Si vas a usar únicamente el productor C++, no necesitas Docker.

## 1. ¿Qué voy a ejecutar?

La demostración completa tiene este recorrido:

**Simulador MQTT → broker Mosquitto → API FastAPI → MySQL → WebSocket → dashboard web**

- **MySQL Server** guarda las lecturas y las alertas. No es necesario instalar Workbench.
- **Mosquitto** es el broker que recibe los mensajes MQTT del simulador.
- **FastAPI** valida los mensajes, consulta y guarda datos, y sirve la página web.
- **El simulador MQTT** genera lecturas ficticias para tres sensores.
- **El dashboard** muestra el estado y las lecturas recibidas.

El C++ es un módulo concurrente adicional con su propio simulador y pruebas. No hace falta
compilarlo para ejecutar la demo MQTT descrita en las secciones principales.

### En palabras sencillas: qué es cada componente

- **Docker Desktop** es el programa que permite ejecutar contenedores en Windows; **Docker
  Compose** lee `src/api_fastapi/compose.yaml`. Para la demo local se usa `docker compose up -d
  mqtt` y arranca solo **Mosquitto**, el broker que recibe y reenvía mensajes MQTT. Para el
  despliegue público, el mismo Compose puede ejecutar FastAPI y Caddy con HTTPS; MySQL siempre
  es externo y la ruta C++ directa a MySQL no requiere Docker.
- **MQTT** es el protocolo de mensajes entre el simulador/publicador y el suscriptor de la API.
  **FastAPI** es el código de la API; **Uvicorn** es el servidor que lo ejecuta y sirve el
  dashboard en el navegador.
- **MySQL Server** es la base persistente. El broker solo transporta mensajes; las lecturas y
  alertas se guardan en MySQL.
- **C++ y MQTT son dos caminos alternativos para ingresar lecturas.** El productor C++ usa
  hilos, cola y consumidores y guarda directamente en MySQL. El simulador MQTT publica al
  broker y la API valida y guarda los mensajes. No hace falta iniciar ambos productores a la vez.
- **REST** son peticiones web para cargar estado e historial; **WebSocket** mantiene un canal
  persistente entre el navegador y FastAPI. Después de la carga inicial, la API consulta MySQL
  y envía por ese canal el estado y las alertas aproximadamente cada 2 segundos, sin que la
  página tenga que solicitarlos repetidamente. WebSocket no conecta el simulador con MySQL ni
  guarda lecturas. Si se desconecta, el dashboard intenta reconectar y consulta REST cada cinco
  segundos temporalmente; REST también se usa para cargar el estado inicial y el historial.
- **`.venv`** es el entorno aislado de Python del proyecto; no contiene el proyecto ni la base
  de datos. Las dependencias Python están declaradas en `requirements.txt`; VS Code y
  Workbench son herramientas opcionales, no servicios que deban permanecer abiertos.
- Los simuladores generan datos ficticios. `sensor_01`, `sensor_02` y `sensor_03` son
  identificadores, no sensores físicos instalados.

## 2. Requisitos e instalaciones

Necesitas conexión a Internet durante la instalación y al menos 5 GB de espacio libre.

1. **Python 3.10 o posterior.** Descárgalo de [python.org](https://www.python.org/downloads/).
   Durante la instalación en Windows, activa **Add Python to PATH**. Comprueba en PowerShell:

   ```powershell
   py --version
   ```

2. **MySQL Server 8.0 o posterior.** Descarga el instalador de
   [MySQL Community Server](https://dev.mysql.com/downloads/mysql/). Instala el servidor y
   conserva el cliente de línea de comandos `mysql`. **MySQL Workbench es opcional** y esta
   guía no depende de él. Durante la configuración:
   - selecciona la configuración de desarrollo local;
   - crea una contraseña de administrador `root` y guárdala en un lugar seguro;
   - deja el servicio de MySQL configurado para iniciarse con Windows.

3. **Docker Desktop para Windows**, necesario para el broker de la ruta MQTT. También se usa
   Docker Engine en un servidor Linux si se desea desplegar para acceso multiusuario:
   [descarga oficial](https://www.docker.com/products/docker-desktop/). Completa la instalación,
   acepta WSL 2 si el instalador lo solicita, abre Docker Desktop y espera hasta que indique
   que el motor está en ejecución. Verifica en PowerShell:

   ```powershell
   docker --version
   docker compose version
   ```

4. **Los archivos del proyecto.** Para clonar, Git debe estar instalado
   ([git-scm.com](https://git-scm.com/download/win)) y el repositorio debe estar publicado y
   accesible:

   ```powershell
   Set-Location $HOME\Documents
   git clone https://github.com/LizbethCarmona/Monitoreo-Ambiental.git
   Set-Location .\Monitoreo-Ambiental
   ```

   Si todavía no puedes clonar el repositorio, usa la carpeta del proyecto que te comparta el
   equipo. En ese caso, abre PowerShell en la carpeta principal, donde están `README.md`, `src`
   y `docs`. Puedes abrir una terminal en una carpeta desde el Explorador de archivos escribiendo
   `powershell` en la barra de dirección.

5. **Editor (opcional).** VS Code facilita abrir los archivos, pero no es necesario para correr
   la demo. MySQL Workbench también es opcional; toda la preparación de la base de datos se hace
   desde el cliente `mysql` incluido con MySQL Server.

## 3. Instalar las dependencias de Python

Abre PowerShell en la carpeta principal del proyecto. Comprueba que estás en el sitio correcto:

```powershell
Get-ChildItem
```

Debes ver `README.md`, `src` y `docs`. Crea un entorno aislado para este proyecto e instala sus
dependencias:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r src\api_fastapi\requirements.txt
```

La carpeta `.venv` contiene Python y las bibliotecas de la aplicación para este proyecto. No
necesitas activar el entorno: en los comandos siguientes se invoca directamente su Python.
La instalación se hace una sola vez por copia del repositorio.

## 4. Preparar MySQL sin Workbench

### 4.1 Comprobar el servicio

Abre una ventana nueva de PowerShell. Para comprobar si Windows ve el servicio de MySQL:

```powershell
Get-Service *mysql*
```

Si aparece un servicio detenido, abre PowerShell como administrador y arráncalo usando el nombre
que te mostró el comando. Por ejemplo, si el nombre es `MySQL80`:

```powershell
Start-Service MySQL80
```

El nombre puede cambiar según la versión instalada. Si no aparece ningún servicio, revisa la
instalación de MySQL Server antes de continuar.

### 4.2 Crear las tablas y los datos iniciales

El instalador de MySQL normalmente instala también el programa de consola `mysql`. Comprueba:

```powershell
Get-Command mysql
```

Si PowerShell encuentra `mysql.exe`, entra a la carpeta de la base de datos e inicia el cliente:

```powershell
Set-Location RUTA\A\LA\CARPETA\DEL\PROYECTO\src\database
mysql -u root -p
```

Reemplaza `RUTA\A\LA\CARPETA\DEL\PROYECTO` por la ruta verdadera de tu copia. Por ejemplo:

```powershell
Set-Location "C:\Users\Ana\Documents\Monitoreo-Ambiental\src\database"
mysql -u root -p
```

Escribe la contraseña de `root` cuando `mysql` la solicite. No se verá mientras la escribes.
Cuando aparezca el indicador `mysql>`, ejecuta:

```sql
SOURCE schema.sql;
```

El esquema crea la base `monitoreo_ambiental`, sus tablas, tres sensores de demostración y los
umbrales iniciales. Al terminar sin errores, prepara un usuario de aplicación con privilegios
limitados. En el ejemplo, **reemplaza** `PON_AQUI_UNA_CLAVE_SEGURA` por una contraseña propia,
entre comillas simples:

```sql
CREATE USER IF NOT EXISTS 'monitoreo_app'@'127.0.0.1'
  IDENTIFIED BY 'PON_AQUI_UNA_CLAVE_SEGURA';
GRANT SELECT, INSERT ON monitoreo_ambiental.*
  TO 'monitoreo_app'@'127.0.0.1';
```

Guarda esa contraseña para el siguiente paso. No uses la cuenta `root` para ejecutar la API y
no guardes la contraseña en archivos del proyecto. Sal del cliente:

```sql
EXIT;
```

**Si `mysql` no se reconoce como comando:** el cliente puede no estar agregado al `PATH`.
Localiza `mysql.exe` en la carpeta de instalación de MySQL (normalmente bajo
`C:\Program Files\MySQL\MySQL Server 8.0\bin\` o
`C:\Program Files\MySQL\MySQL Server 8.4\bin\`). En PowerShell, cambia primero a la carpeta
`src\database` de tu proyecto y ejecuta el cliente con su ruta completa, por ejemplo:

```powershell
Set-Location "RUTA\A\LA\CARPETA\DEL\PROYECTO\src\database"
& "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe" -u root -p
```

Si tu carpeta dice `8.0` en lugar de `8.4`, cambia la ruta. Ya en `mysql>`, ejecuta
`SOURCE schema.sql;` y luego los comandos `CREATE USER` y `GRANT` de arriba.

> Si el proyecto ya se había instalado y contiene datos, **no borres la base ni vuelvas a
> ejecutar instrucciones destructivas**. `schema.sql` crea objetos faltantes, pero los umbrales
> existentes no se sobrescriben. Para una primera instalación nueva, el propio esquema ya
> establece PM2.5 promedio de 24 horas en 25 µg/m³ (fase Año 5); no necesitas ejecutar la
> migración `actualizar_umbrales_verificados.sql`.

## 5. Iniciar la demo completa

Se usan dos terminales de PowerShell. Antes de comenzar, confirma que MySQL está iniciado y que
Docker Desktop muestra su motor en ejecución. Docker Compose inicia un contenedor local de
Mosquitto para transportar las lecturas MQTT; la API, MySQL y el dashboard se ejecutan por
separado. Si eliges la ruta C++ directa a MySQL en vez de MQTT, no hace falta iniciar Docker.
Las variables `MYSQL_*` se configuran en la **Terminal 1**, y Uvicorn debe iniciarse desde esa
misma terminal: PowerShell no las comparte con otra ventana. La Terminal 2 se usa para el
simulador; no es necesario configurar las variables MySQL allí.

### Terminal 1: iniciar el broker y la API

Abre una terminal y pega estos comandos. Escribe la contraseña de `monitoreo_app` cuando se te
solicite:

```powershell
Set-Location "RUTA\A\LA\CARPETA\DEL\PROYECTO"
$env:MYSQL_HOST = "127.0.0.1"
$env:MYSQL_PORT = "3306"
$env:MYSQL_USER = "monitoreo_app"
$env:MYSQL_DATABASE = "monitoreo_ambiental"
$clave = Read-Host "Contraseña de monitoreo_app" -AsSecureString
$env:MYSQL_PASSWORD = [System.Net.NetworkCredential]::new("", $clave).Password

Set-Location .\src\api_fastapi
docker compose up -d mqtt

$env:MQTT_ENABLED = "true"
$env:MQTT_HOST = "127.0.0.1"
$env:MQTT_PORT = "1883"
..\..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Cambia `RUTA\A\LA\CARPETA\DEL\PROYECTO` por la ruta real. Por ejemplo, si tienes el proyecto
en `C:\Users\Ana\Documents\Monitoreo-Ambiental`, reemplaza la primera línea por:

```powershell
Set-Location "C:\Users\Ana\Documents\Monitoreo-Ambiental"
```

Deja abierta esta terminal mientras enseñas la demo. La API está lista cuando Uvicorn informa
que se inició y muestra que escucha en `http://127.0.0.1:8000`.

### Terminal 2: generar y enviar lecturas sintéticas

Abre otra ventana de PowerShell. Usa la misma ruta real del proyecto:

```powershell
Set-Location "RUTA\A\LA\CARPETA\DEL\PROYECTO\src\api_fastapi"
..\..\.venv\Scripts\python.exe -m app.simulador_mqtt --sensores 3 --intervalo 2
```

Déjala ejecutándose. Cada dos segundos el simulador publica datos ficticios para tres sensores.
Pulsa `Ctrl+C` en esta terminal para detenerlo.

## 6. Verificar que funciona

Abre el navegador y visita:

- **Dashboard:** [http://127.0.0.1:8000/dashboard/](http://127.0.0.1:8000/dashboard/)
- **Estado de conexiones:** [http://127.0.0.1:8000/salud](http://127.0.0.1:8000/salud)
- **Lecturas y estado:** [http://127.0.0.1:8000/estado-clima](http://127.0.0.1:8000/estado-clima)
- **Documentación de la API:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

En `/salud`, MySQL debe aparecer conectado y MQTT conectado. En el dashboard deben empezar a
actualizarse los valores después de iniciar el simulador. Si todavía no aparecen lecturas,
espera unos segundos y vuelve a cargar el dashboard.

El recorrido para explicarlo es:
**simulador → MQTT → API → MySQL → WebSocket → dashboard**.

### Entender el dashboard y el historial

- **Fuente:** identifica el sensor que envió la lectura más reciente almacenada. Por ejemplo,
  `sensor_03` es el identificador del sensor; cuando se usa el simulador, la lectura es
  sintética y no proviene de un dispositivo físico.
- **Lecturas por hora:** cada fila corresponde a una hora UTC con datos. Muestra por separado
  el promedio horario de PM2.5, su estado orientativo y la temperatura promedio. El color
  clasifica solo PM2.5; si solo hay datos en una hora, es normal que aparezca una fila.
- **Alertas activas:** la tarjeta conserva su propio borde y la lista se desplaza dentro del
  panel cuando hay muchas alertas. La vista activa muestra hasta 20 recientes; el enlace
  **Ver historial (100 recientes)** cambia a las últimas 100 alertas. En móvil, desplázate
  dentro de la lista para recorrerla; también puedes desplazarte por la página fuera de ella.
- Para ver un historial recién limpiado, detén los productores antes de borrar los registros
  y recarga el dashboard con `Ctrl+F5`. Las lecturas y alertas nuevas volverán a aparecer al
  iniciar un productor.

## 7. Detener el proyecto

1. Pulsa `Ctrl+C` en la terminal del simulador.
2. Pulsa `Ctrl+C` en la terminal de Uvicorn.
3. En PowerShell, detén el broker:

   ```powershell
   Set-Location "RUTA\A\LA\CARPETA\DEL\PROYECTO\src\api_fastapi"
   docker compose down
   ```

No uses `docker compose down -v`: esa opción elimina volúmenes de datos asociados si en el
futuro se agregan al Compose. Detener la aplicación no borra las lecturas; estas permanecen
guardadas en MySQL.

### Dejar vacío el historial del dashboard (opcional)

La API obtiene el historial directamente de las tablas MySQL `lecturas` y `alertas`. Para
dejarlo vacío, primero detén el simulador MQTT y cualquier productor C++; si siguen activos,
insertarán registros nuevos. No borres tablas ni archivos de MySQL: elimina solo las filas desde
Workbench o el cliente `mysql`.

El 15-oct-2026 se limpió la instancia local de demostración. MySQL confirmó que se eliminaron
15,040 alertas y 32,344 lecturas y que ambas tablas quedaron en cero. Esas cantidades pertenecen
a esa instancia; en otra instalación, consulta los conteos antes de eliminar:

Para ejecutar los `DELETE`, inicia sesión con una cuenta administradora o con una cuenta que
tenga permiso `DELETE` sobre este esquema. La cuenta de aplicación de la API solo necesita
`SELECT` e `INSERT`; no le agregues permisos de borrado para realizar esta limpieza.

```sql
USE monitoreo_ambiental;
SELECT COUNT(*) AS lecturas_antes FROM lecturas;
SELECT COUNT(*) AS alertas_antes FROM alertas;
```

Si confirmas que esa es la base correcta y quieres borrar todo su historial, ejecuta:

```sql
START TRANSACTION;
DELETE FROM alertas WHERE alerta_id > 0;
DELETE FROM lecturas WHERE lectura_id > 0;
SELECT COUNT(*) AS lecturas_despues FROM lecturas;
SELECT COUNT(*) AS alertas_despues FROM alertas;
```

Ejecuta `COMMIT;` solo si ambas consultas posteriores devuelven cero. Si los resultados no son
los esperados, usa `ROLLBACK;` en lugar de confirmar. La limpieza conserva las tablas, sensores
y umbrales. Al terminar, recarga el dashboard con `Ctrl+F5`; si aparecen valores anteriores en
pantalla, detén y reinicia la API y vuelve a cargar la página. Con el simulador detenido, el
historial seguirá vacío. Cuando lo vuelvas a iniciar, se guardarán lecturas y podrán generarse
alertas nuevas.

Eliminar filas sirve para limpiar el historial; no necesariamente reduce el tamaño físico de
MySQL en el disco. El espacio queda disponible para reutilizarse.

## 8. Preguntas y problemas comunes

### «`py` no se reconoce»

Python no quedó instalado o el lanzador no está en el `PATH`. Instala Python desde
[python.org](https://www.python.org/downloads/), marca **Add Python to PATH**, cierra y vuelve
a abrir PowerShell, y prueba `py --version`.

### «No se encuentra `mysql`»

MySQL Server o el cliente de línea de comandos no está instalado, o su carpeta `bin` no está en
el `PATH`. Sigue la sección 4.2 y ejecuta `mysql.exe` con su ruta completa. No hace falta
Workbench.

### «Access denied for user `monitoreo_app`»

Comprueba que escribiste la contraseña que creaste y que configuraste
`MYSQL_USER=monitoreo_app` y `MYSQL_HOST=127.0.0.1`. Si la cuenta no existe o su contraseña se
escribió mal al crearla, vuelve a MySQL como `root` para corregir la cuenta y los permisos.
No pegues ni envíes la contraseña en un chat.

### «No se puede conectar a MySQL»

Comprueba que el servicio está iniciado con `Get-Service *mysql*`, que MySQL usa el puerto 3306
y que las variables `MYSQL_HOST`, `MYSQL_PORT` y `MYSQL_DATABASE` están configuradas en **la
misma terminal** donde arrancas Uvicorn.

### «`docker` no se reconoce» o Docker no conecta

Instala y abre Docker Desktop, espera a que el motor esté listo, y verifica `docker --version`
y `docker compose version`. Si acabas de instalar Docker, cierra y vuelve a abrir PowerShell.

### El puerto 1883 o 8000 ya está ocupado

Cierra la aplicación que está usando el puerto o detén la instancia anterior del proyecto.
Uvicorn debe escuchar en 8000 y Mosquitto en 1883 para usar los comandos de esta guía.

### El navegador abre la página, pero no hay datos nuevos

Comprueba que la terminal del simulador sigue activa y que `/salud` muestra MySQL y MQTT
conectados. Revisa también que la API y el simulador se iniciaron desde las rutas de esta guía.

### La aplicación se queja de que falta `MYSQL_PASSWORD`

Define las variables de conexión en la misma ventana de PowerShell desde la que inicias la API.
Las variables no se transfieren automáticamente entre terminales distintas. Si Uvicorn ya está
ejecutándose en otra terminal, pulsa `Ctrl+C` allí y vuelve a iniciarlo desde la ventana donde
configuraste `MYSQL_PASSWORD`.

## 9. Ejecutar las pruebas automáticas de la API (opcional)

Para instalar también las dependencias de pruebas, desde la carpeta principal ejecuta:

```powershell
.\.venv\Scripts\python.exe -m pip install -r src\api_fastapi\requirements-dev.txt
```

Luego:

```powershell
Set-Location "RUTA\A\LA\CARPETA\DEL\PROYECTO\src\api_fastapi"
..\..\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

La prueba que usa un broker real es opcional: necesita iniciar Mosquitto y definir
`$env:MQTT_TEST_BROKER = "127.0.0.1"` antes de lanzar las pruebas.

## 10. Ejecutar el módulo C++ (opcional)

El módulo C++ también genera datos sintéticos, pero compilarlo en Windows requiere MSYS2
UCRT64 con `g++`, `make`, `pkgconf` y el cliente C de MariaDB. No es un requisito para la demo
MQTT de este manual. La compilación, las pruebas de concurrencia y la configuración de MySQL
están explicadas en [README del núcleo C++](../src/cpp_ingestion/README.md).

## 11. Qué significan los datos y las alertas

- **Lectura** es una medición individual recibida y guardada; **promedio móvil** resume lecturas
  dentro de una ventana (por ejemplo, 8 o 24 horas). El dashboard agrupa lecturas por hora UTC
  y solo muestra las horas que tienen datos.
- Las **alertas** guardadas se generan por superar un umbral de una lectura individual. Los
  promedios móviles se presentan aparte y no crean alertas persistidas en esta versión.
  “Alertas activas” son las filas no atendidas; “historial” incluye alertas atendidas y no
  atendidas. La lista activa muestra hasta 20 recientes y el historial hasta 100.
- Los valores del simulador no son mediciones físicas, pronósticos del clima ni resultados
  certificados.
- PM2.5, CO₂ y temperatura tienen reglas de demostración y referencias que se describen en
  [README de la base de datos](../src/database/README.md).
- PM2.5 promedio de 24 horas usa 25 µg/m³ como referencia de fase Año 5, aplicable al estado
  del proyecto al 14 de octubre de 2026. Los niveles instantáneos del prototipo no son límites
  de alerta definidos por la NOM-025.
- Las referencias de CO₂ citadas son ocupacionales y no deben interpretarse como umbrales
  instantáneos de calidad de aire ambiental.
- Las alertas del prototipo corresponden a lecturas puntuales; los promedios móviles aparecen
  como métricas separadas.

Para consultar los resultados de las pruebas y su alcance, lee el
[informe de pruebas](informe_pruebas.md). Para la secuencia preparada para presentar el sistema,
consulta el [guion de demostración](guion_demo.md).
