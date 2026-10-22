// Dashboard — Monitoreo ambiental en tiempo real
//
// Consume la API FastAPI y recibe estado/alertas por WebSocket.

const NIVEL_A_CLASE = {
  normal: "green",
  advertencia: "amber",
  critico: "red",
};

const NIVEL_A_ETIQUETA = {
  normal: "Normal",
  advertencia: "Advertencia",
  critico: "Crítico",
};

let mostrandoHistorial = false;
let sondeoCompatibilidad = null;
let esperaReconectarWebSocket = 3000;
const mensajeFuente = document.getElementById("app-footer").textContent.trim();

async function obtenerJSON(ruta) {
  const resp = await fetch(ruta, { cache: "no-store" });
  if (!resp.ok) throw new Error(`${ruta} -> HTTP ${resp.status}`);
  return resp.json();
}

function pintarEstadoClima(datos) {
  const mostrar = (valor, sufijo = "") =>
    valor === null || valor === undefined ? "—" : `${valor}${sufijo}`;
  const historialHorario = datos.historial_horario ?? datos.pronostico_horario;
  if (!Array.isArray(historialHorario)) {
    throw new Error("La API no devolvió el arreglo de observaciones horarias.");
  }
  const apiConClasificacion =
    Object.prototype.hasOwnProperty.call(datos, "pm2_5_nivel") &&
    Object.prototype.hasOwnProperty.call(datos, "co2_nivel");

  document.getElementById("subtitulo").textContent =
    `${datos.ciudad} · ${datos.sensores_activos} sensores activos`;
  document.getElementById("ciudad").textContent = datos.ciudad;
  document.getElementById("fecha").textContent = datos.fecha;
  document.getElementById("temp-actual").textContent =
    datos.temperatura_actual === null ? "—°" : `${Math.round(datos.temperatura_actual)}°`;
  const hayLectura = datos.temperatura_actual != null || datos.pm2_5 != null || datos.co2 != null;
  document.getElementById("lectura-info").textContent = datos.sensor_ultima_lectura
    ? `Fuente: ${datos.sensor_ultima_lectura} · ${datos.hora_ultima_lectura_utc}`
    : hayLectura
      ? "Última lectura recibida · sensor no informado por la API"
      : "Sin lecturas registradas";
  document.getElementById("temp-range").textContent =
    datos.temperatura_min === null || datos.temperatura_max === null
      ? "Sin lecturas registradas hoy"
      : `Mín ${Math.round(datos.temperatura_min)}° · Máx ${Math.round(datos.temperatura_max)}° hoy`;

  const claseAire = apiConClasificacion ? (NIVEL_A_CLASE[datos.calidad_aire_nivel] || "green") : "gray";
  document.getElementById("calidad-texto").textContent = apiConClasificacion
    ? `Calidad del aire: ${datos.calidad_aire}`
    : "Calidad del aire: clasificación no disponible";
  document.getElementById("calidad-badge").querySelector(".dot").className = `dot ${claseAire}`;

  document.getElementById("pm25").textContent = mostrar(datos.pm2_5, " µg/m³");
  document.getElementById("co2").textContent = mostrar(datos.co2, " ppm");
  document.getElementById("pm25-24h").textContent = mostrar(datos.pm2_5_promedio_24h, " µg/m³");
  document.getElementById("pm25-24h-label").textContent =
    `PM2.5 promedio 24 h (límite ${mostrar(datos.pm2_5_limite_24h)})`;

  document.getElementById("dot-pm25").className =
    `dot ${apiConClasificacion ? NIVEL_A_CLASE[datos.pm2_5_nivel] || "green" : "gray"}`;
  document.getElementById("dot-co2").className =
    `dot ${apiConClasificacion ? NIVEL_A_CLASE[datos.co2_nivel] || "green" : "gray"}`;
  document.getElementById("dot-pm25-24h").className =
    `dot ${apiConClasificacion ? NIVEL_A_CLASE[datos.pm2_5_promedio_24h_nivel] || "green" : "gray"}`;

  const fila = document.getElementById("hourly-row");
  fila.innerHTML = "";
  if (historialHorario.length === 0) {
    const filaVacia = document.createElement("tr");
    const mensaje = document.createElement("td");
    mensaje.className = "hourly-empty";
    mensaje.colSpan = 4;
    mensaje.textContent = "No hay lecturas registradas en las últimas 24 horas.";
    filaVacia.appendChild(mensaje);
    fila.appendChild(filaVacia);
  }
  for (const punto of historialHorario) {
    const filaHora = document.createElement("tr");
    if (punto.actual) filaHora.className = "hourly-current";

    const hora = document.createElement("th");
    hora.scope = "row";
    hora.dataset.label = "Hora (UTC)";
    hora.textContent = `${punto.fecha} · ${punto.hora}`;
    if (punto.actual) {
      hora.appendChild(document.createElement("br"));
      const actual = document.createElement("span");
      actual.className = "hourly-current-label";
      actual.textContent = "Última hora con datos";
      hora.appendChild(actual);
    }

    const pm25 = document.createElement("td");
    pm25.dataset.label = "PM2.5 promedio (µg/m³)";
    pm25.textContent = mostrar(punto.pm25, " µg/m³");

    const estado = document.createElement("td");
    estado.dataset.label = "Estado de PM2.5";
    const status = document.createElement("span");
    status.className = "hour-status";
    const dot = document.createElement("span");
    dot.className = `dot ${punto.pm25 == null || !apiConClasificacion
      ? "gray"
      : NIVEL_A_CLASE[punto.nivel] || "gray"}`;
    const statusText = document.createElement("span");
    statusText.textContent = punto.pm25 == null
      ? "Sin dato"
      : apiConClasificacion
        ? NIVEL_A_ETIQUETA[punto.nivel] || "Clasificación no disponible"
        : "Clasificación no disponible";
    status.append(dot, statusText);
    estado.appendChild(status);

    const temperatura = document.createElement("td");
    temperatura.dataset.label = "Temperatura promedio (°C)";
    temperatura.textContent = mostrar(punto.temp, " °C");

    filaHora.append(hora, pm25, estado, temperatura);
    fila.appendChild(filaHora);
  }
}

function pintarAlertas(datos) {
  document.getElementById("alert-count").textContent = datos.total;
  document.getElementById("alerts-heading").textContent =
    mostrandoHistorial ? "Historial de alertas" : "Alertas activas";
  const lista = document.getElementById("alerts-list");
  lista.innerHTML = "";

  if (datos.alertas.length === 0) {
    const mensaje = document.createElement("li");
    mensaje.className = "muted small";
    mensaje.style.padding = "12px 0";
    mensaje.textContent = mostrandoHistorial ? "Sin alertas registradas" : "Sin alertas activas";
    lista.appendChild(mensaje);
    return;
  }

  for (const alerta of datos.alertas) {
    const clase = NIVEL_A_CLASE[alerta.nivel] || "amber";
    const etiqueta = NIVEL_A_ETIQUETA[alerta.nivel] || alerta.nivel;
    const li = document.createElement("li");
    li.className = "alert-item";
    const izquierda = document.createElement("div");
    izquierda.className = "alert-left";
    const punto = document.createElement("span");
    punto.className = `dot ${clase}`;
    const texto = document.createElement("div");
    const titulo = document.createElement("div");
    titulo.className = "alert-title";
    titulo.textContent = alerta.titulo;
    const detalle = document.createElement("div");
    detalle.className = `alert-sub ${alerta.nivel}`;
    detalle.textContent = `${alerta.hora} · ${etiqueta}${alerta.estado ? ` · ${alerta.estado}` : ""}`;
    texto.append(titulo, detalle);
    izquierda.append(punto, texto);

    const derecha = document.createElement("div");
    derecha.className = "alert-right";
    derecha.append(document.createTextNode(`${alerta.valor_medido} / ${alerta.valor_limite} `));
    const unidad = document.createElement("span");
    unidad.className = "alert-unit";
    unidad.textContent = alerta.unidad;
    derecha.appendChild(unidad);
    li.append(izquierda, derecha);
    lista.appendChild(li);
  }
}

async function refrescarAlertas() {
  const ruta = mostrandoHistorial ? "/alertas/historial?limite=100" : "/alertas";
  pintarAlertas(await obtenerJSON(ruta));
}

async function refrescar() {
  try {
    const clima = await obtenerJSON("/estado-clima");
    pintarEstadoClima(clima);
    await refrescarAlertas();
    document.getElementById("app-footer").textContent = mensajeFuente;
  } catch (err) {
    console.error("No se pudo refrescar el dashboard:", err);
    document.getElementById("app-footer").textContent =
      "No se pudo contactar la API. Verifica que MySQL y uvicorn estén disponibles.";
  }
}

function conectarWebSocket() {
  const estado = document.getElementById("live-status");
  const esquema = location.protocol === "https:" ? "wss:" : "ws:";
  const socket = new WebSocket(`${esquema}//${location.host}/ws/dashboard`);
  let latido;

  socket.addEventListener("open", () => {
    esperaReconectarWebSocket = 3000;
    if (sondeoCompatibilidad !== null) {
      clearInterval(sondeoCompatibilidad);
      sondeoCompatibilidad = null;
    }
    estado.innerHTML = '<span class="dot green pulse"></span> En vivo · WebSocket';
    latido = setInterval(() => {
      if (socket.readyState === WebSocket.OPEN) socket.send("ping");
    }, 20000);
  });

  socket.addEventListener("message", (event) => {
    try {
      const mensaje = JSON.parse(event.data);
      if (mensaje.tipo === "actualizacion") {
        pintarEstadoClima(mensaje.estado);
        if (!mostrandoHistorial) pintarAlertas(mensaje.alertas);
        document.getElementById("app-footer").textContent = mensajeFuente;
      } else if (mensaje.tipo === "error") {
        document.getElementById("app-footer").textContent = mensaje.mensaje;
      }
    } catch (error) {
      console.error("La API envio un mensaje WebSocket invalido:", error);
      document.getElementById("app-footer").textContent =
        "La API envió una actualización inválida; revisa sus registros.";
    }
  });

  socket.addEventListener("close", () => {
    clearInterval(latido);
    estado.innerHTML = '<span class="dot amber"></span> REST provisional · reconectando WebSocket…';
    if (sondeoCompatibilidad === null) {
      sondeoCompatibilidad = setInterval(refrescar, 5000);
    }
    setTimeout(conectarWebSocket, esperaReconectarWebSocket);
    esperaReconectarWebSocket = Math.min(esperaReconectarWebSocket * 2, 30000);
  });

  socket.addEventListener("error", () => socket.close());
}

document.getElementById("ver-historial").addEventListener("click", async (event) => {
  event.preventDefault();
  mostrandoHistorial = !mostrandoHistorial;
  const enlace = document.getElementById("ver-historial");
  enlace.textContent = mostrandoHistorial
    ? "Volver a alertas activas"
    : "Ver historial (100 recientes) →";
  try {
    await refrescarAlertas();
  } catch (err) {
    console.error("No se pudo cargar el historial de alertas:", err);
    mostrandoHistorial = false;
    enlace.textContent = "Ver historial (100 recientes) →";
    document.getElementById("alerts-heading").textContent = "Alertas activas";
    const lista = document.getElementById("alerts-list");
    lista.innerHTML = "";
    const mensaje = document.createElement("li");
    mensaje.className = "muted small";
    mensaje.style.padding = "12px 0";
    mensaje.textContent = String(err).includes("HTTP 404")
      ? "El historial requiere reiniciar la API para cargar el endpoint actualizado."
      : "No se pudo cargar el historial; verifica que la API y MySQL estén disponibles.";
    lista.appendChild(mensaje);
    document.getElementById("app-footer").textContent = mensaje.textContent;
  }
});

refrescar();
conectarWebSocket();
