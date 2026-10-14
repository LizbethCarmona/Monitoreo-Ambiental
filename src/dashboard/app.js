// Dashboard — Monitoreo ambiental en tiempo real
//
// Consume la API FastAPI (src/api_fastapi) sirviendo este dashboard como
// archivos estaticos montados en la misma app (ver app/main.py), para evitar
// problemas de CORS. Hace polling simple cada 5s para simular "tiempo real"
// mientras no existe el WebSocket (planeado para el Sprint 3, Semana 6).

const REFRESCO_MS = 5000;

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

async function obtenerJSON(ruta) {
  const resp = await fetch(ruta, { cache: "no-store" });
  if (!resp.ok) throw new Error(`${ruta} -> HTTP ${resp.status}`);
  return resp.json();
}

function pintarEstadoClima(datos) {
  document.getElementById("subtitulo").textContent =
    `${datos.ciudad} · ${datos.sensores_activos} sensores activos`;
  document.getElementById("ciudad").textContent = datos.ciudad;
  document.getElementById("fecha").textContent = datos.fecha;
  document.getElementById("temp-actual").textContent = `${Math.round(datos.temperatura_actual)}°`;
  document.getElementById("temp-range").textContent =
    `Mín ${Math.round(datos.temperatura_min)}° · Máx ${Math.round(datos.temperatura_max)}° hoy`;

  const claseAire = NIVEL_A_CLASE[datos.calidad_aire_nivel] || "green";
  document.getElementById("calidad-texto").textContent = `Calidad del aire: ${datos.calidad_aire}`;
  document.getElementById("calidad-badge").querySelector(".dot").className = `dot ${claseAire}`;

  document.getElementById("pm25").textContent = `${datos.pm2_5} µg/m³`;
  document.getElementById("co2").textContent = `${datos.co2} ppm`;
  document.getElementById("pm25-24h").textContent = `${datos.pm2_5_promedio_24h} µg/m³`;
  document.getElementById("pm25-24h-label").textContent =
    `PM2.5 promedio 24 h (límite ${datos.pm2_5_limite_24h})`;

  document.getElementById("dot-pm25").className = `dot ${NIVEL_A_CLASE[datos.pm2_5_nivel] || "green"}`;
  document.getElementById("dot-co2").className = `dot ${NIVEL_A_CLASE[datos.co2_nivel] || "green"}`;
  document.getElementById("dot-pm25-24h").className = `dot ${NIVEL_A_CLASE[datos.pm2_5_promedio_24h_nivel] || "green"}`;

  const fila = document.getElementById("hourly-row");
  fila.innerHTML = "";
  for (const punto of datos.pronostico_horario) {
    const slot = document.createElement("div");
    slot.className = "hour-slot" + (punto.actual ? " active" : "");
    slot.innerHTML = `
      <span class="hour-label">${punto.hora}</span>
      <span class="dot hour-dot ${NIVEL_A_CLASE[punto.nivel] || "green"}"></span>
      <span class="hour-temp">${Math.round(punto.temp)}°</span>
    `;
    fila.appendChild(slot);
  }
}

function pintarAlertas(datos) {
  document.getElementById("alert-count").textContent = datos.total;
  const lista = document.getElementById("alerts-list");
  lista.innerHTML = "";

  if (datos.alertas.length === 0) {
    lista.innerHTML = '<li class="muted small" style="padding:12px 0;">Sin alertas activas</li>';
    return;
  }

  for (const alerta of datos.alertas) {
    const clase = NIVEL_A_CLASE[alerta.nivel] || "amber";
    const etiqueta = NIVEL_A_ETIQUETA[alerta.nivel] || alerta.nivel;
    const li = document.createElement("li");
    li.className = "alert-item";
    li.innerHTML = `
      <div class="alert-left">
        <span class="dot ${clase}"></span>
        <div>
          <div class="alert-title">${alerta.titulo}</div>
          <div class="alert-sub ${alerta.nivel}">${alerta.hora} · ${etiqueta}</div>
        </div>
      </div>
      <div class="alert-right">
        ${alerta.valor_medido} / ${alerta.valor_limite}
        <span class="alert-unit">${alerta.unidad}</span>
      </div>
    `;
    lista.appendChild(li);
  }
}

async function refrescar() {
  try {
    const [clima, alertas] = await Promise.all([
      obtenerJSON("/estado-clima"),
      obtenerJSON("/alertas"),
    ]);
    pintarEstadoClima(clima);
    pintarAlertas(alertas);
  } catch (err) {
    console.error("No se pudo refrescar el dashboard:", err);
    document.getElementById("app-footer").textContent =
      "No se pudo contactar la API en /estado-clima o /alertas. ¿Esta corriendo uvicorn?";
  }
}

refrescar();
setInterval(refrescar, REFRESCO_MS);
