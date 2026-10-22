#include "ThreadPoolConsumidor.hpp"
#include <iostream>

ThreadPoolConsumidor::ThreadPoolConsumidor(int num_workers, ColaConcurrente& cola, DatabaseManager& db)
    : num_workers_(num_workers), cola_(cola), db_(db), umbrales_(db.cargarUmbralesLectura()) {}

void ThreadPoolConsumidor::iniciar() {
    trabajadores_.reserve(num_workers_);
    for (int i = 0; i < num_workers_; ++i) {
        trabajadores_.emplace_back(&ThreadPoolConsumidor::procesarMetricas, this);
    }
}

void ThreadPoolConsumidor::esperarFinalizacion() {
    for (auto& hilo : trabajadores_) {
        if (hilo.joinable()) hilo.join();
    }
}

void ThreadPoolConsumidor::procesarMetricas() {
    // pop() bloquea sin gastar CPU mientras la cola está vacía, y devuelve
    // std::nullopt únicamente cuando la cola fue cerrada y ya no hay más
    // datos pendientes: esa es la señal para que este trabajador termine.
    while (auto dato_opt = cola_.pop()) {
        const MetricaSensor& dato = *dato_opt;

        Alerta alerta;
        bool hay_alerta = evaluarUmbrales(dato, alerta);

        if (!db_.guardarLecturaTransaccional(dato, hay_alerta ? &alerta : nullptr)) {
            total_errores_persistencia_.fetch_add(1, std::memory_order_relaxed);
            std::cerr << "[error] No se pudo guardar lectura de " << dato.sensor_id
                      << " (" << dato.timestamp << "): " << db_.ultimoError() << std::endl;
            continue;
        }

        calcularPromediosParalelo(dato);
        total_procesadas_.fetch_add(1, std::memory_order_relaxed);
        if (hay_alerta) total_alertas_.fetch_add(1, std::memory_order_relaxed);
    }
}

void ThreadPoolConsumidor::calcularPromediosParalelo(const MetricaSensor& dato) {
    // Único punto de sincronización entre los trabajadores: el acumulador
    // compartido. AcumuladorAgregados protege internamente esta operación
    // con un mutex (ver sección 3.1 del Documento de Justificación).
    agregados_.registrar(dato.sensor_id, dato.pm2_5, dato.co2, dato.tmp);
}

bool ThreadPoolConsumidor::evaluarUmbrales(const MetricaSensor& dato, Alerta& salida) const {
    auto supera = [this](const std::string& metrica, const std::string& nivel, double valor) {
        auto por_metrica = umbrales_.find(metrica);
        if (por_metrica == umbrales_.end()) return false;
        auto limite = por_metrica->second.find(nivel);
        return limite != por_metrica->second.end() && valor >= limite->second;
    };
    auto limite = [this](const std::string& metrica, const std::string& nivel) {
        auto por_metrica = umbrales_.find(metrica);
        if (por_metrica == umbrales_.end()) return 0.0;
        auto valor = por_metrica->second.find(nivel);
        return valor == por_metrica->second.end() ? 0.0 : valor->second;
    };

    // Se evalúa primero el nivel crítico de cada métrica y, si no aplica, el
    // de advertencia. Cada trabajador evalúa su propio dato de forma
    // independiente: no hay necesidad de bloquear nada aquí porque "dato" es
    // una copia local extraída de la cola.
    if (supera("pm25", "critico", dato.pm2_5)) {
        salida = {dato.sensor_id, "pm25", "critico", dato.pm2_5, limite("pm25", "critico"), "PM2.5 sobre umbral critico"};
        return true;
    }
    if (supera("co2", "critico", dato.co2)) {
        salida = {dato.sensor_id, "co2", "critico", dato.co2, limite("co2", "critico"), "CO2 sobre umbral critico"};
        return true;
    }
    if (supera("tmp", "critico", dato.tmp)) {
        salida = {dato.sensor_id, "tmp", "critico", dato.tmp, limite("tmp", "critico"), "Temperatura sobre umbral critico"};
        return true;
    }
    if (supera("pm25", "advertencia", dato.pm2_5)) {
        salida = {dato.sensor_id, "pm25", "advertencia", dato.pm2_5, limite("pm25", "advertencia"), "PM2.5 sobre umbral de advertencia"};
        return true;
    }
    if (supera("co2", "advertencia", dato.co2)) {
        salida = {dato.sensor_id, "co2", "advertencia", dato.co2, limite("co2", "advertencia"), "CO2 sobre umbral de advertencia"};
        return true;
    }
    if (supera("tmp", "advertencia", dato.tmp)) {
        salida = {dato.sensor_id, "tmp", "advertencia", dato.tmp, limite("tmp", "advertencia"), "Temperatura sobre umbral de advertencia"};
        return true;
    }
    return false;
}
