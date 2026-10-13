#include "ThreadPoolConsumidor.hpp"
#include "Umbrales.hpp"
#include <sstream>

ThreadPoolConsumidor::ThreadPoolConsumidor(int num_workers, ColaConcurrente& cola, DatabaseManager& db)
    : num_workers_(num_workers), cola_(cola), db_(db) {}

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

        calcularPromediosParalelo(dato);

        Alerta alerta;
        bool hay_alerta = evaluarUmbrales(dato, alerta);

        db_.guardarLecturaTransaccional(dato, hay_alerta ? &alerta : nullptr);

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
    using namespace umbrales;

    // Se evalúa primero el nivel crítico de cada métrica y, si no aplica, el
    // de advertencia. Cada trabajador evalúa su propio dato de forma
    // independiente: no hay necesidad de bloquear nada aquí porque "dato" es
    // una copia local extraída de la cola.
    if (dato.pm2_5 >= PM25_CRITICO) {
        salida = {dato.sensor_id, "pm25", "critico", dato.pm2_5, PM25_CRITICO, "PM2.5 sobre umbral critico"};
        return true;
    }
    if (dato.co2 >= CO2_CRITICO) {
        salida = {dato.sensor_id, "co2", "critico", dato.co2, CO2_CRITICO, "CO2 sobre umbral critico"};
        return true;
    }
    if (dato.tmp >= TMP_CRITICO) {
        salida = {dato.sensor_id, "tmp", "critico", dato.tmp, TMP_CRITICO, "Temperatura sobre umbral critico"};
        return true;
    }
    if (dato.pm2_5 >= PM25_ADVERTENCIA) {
        salida = {dato.sensor_id, "pm25", "advertencia", dato.pm2_5, PM25_ADVERTENCIA, "PM2.5 sobre umbral de advertencia"};
        return true;
    }
    if (dato.co2 >= CO2_ADVERTENCIA) {
        salida = {dato.sensor_id, "co2", "advertencia", dato.co2, CO2_ADVERTENCIA, "CO2 sobre umbral de advertencia"};
        return true;
    }
    if (dato.tmp >= TMP_ADVERTENCIA) {
        salida = {dato.sensor_id, "tmp", "advertencia", dato.tmp, TMP_ADVERTENCIA, "Temperatura sobre umbral de advertencia"};
        return true;
    }
    return false;
}
