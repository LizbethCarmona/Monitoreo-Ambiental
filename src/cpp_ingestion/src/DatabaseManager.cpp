#include "DatabaseManager.hpp"
#include <stdexcept>

DatabaseManager::DatabaseManager(const std::string& directorio_salida) {
    lecturas_log_.open(directorio_salida + "/lecturas.log", std::ios::app);
    alertas_log_.open(directorio_salida + "/alertas.log", std::ios::app);
    if (!lecturas_log_.is_open() || !alertas_log_.is_open()) {
        throw std::runtime_error("DatabaseManager: no se pudieron abrir los archivos de bitacora");
    }
}

bool DatabaseManager::guardarLecturaTransaccional(const MetricaSensor& dato, const Alerta* alerta_opcional) {
    // Todo el bloque "transaccional" (lectura + alerta) ocurre bajo un único
    // lock: o se escriben ambas filas, o ninguna llega a quedar a medias,
    // igual que el START TRANSACTION / COMMIT documentado en schema.sql.
    std::lock_guard<std::mutex> lock(mtx_);

    lecturas_log_ << dato.toJson() << '\n';
    if (!lecturas_log_.good()) return false;
    ++total_lecturas_;

    if (alerta_opcional != nullptr) {
        alertas_log_ << "{\"sensor_id\":\"" << alerta_opcional->sensor_id << "\","
                     << "\"metrica\":\"" << alerta_opcional->metrica << "\","
                     << "\"nivel\":\"" << alerta_opcional->nivel << "\","
                     << "\"valor_medido\":" << alerta_opcional->valor_medido << ","
                     << "\"valor_limite\":" << alerta_opcional->valor_limite << ","
                     << "\"mensaje\":\"" << alerta_opcional->mensaje << "\"}" << '\n';
        if (!alertas_log_.good()) return false;
        ++total_alertas_;
    }

    lecturas_log_.flush();
    alertas_log_.flush();
    return true;
}

long DatabaseManager::totalLecturasGuardadas() const {
    std::lock_guard<std::mutex> lock(mtx_);
    return total_lecturas_;
}

long DatabaseManager::totalAlertasGuardadas() const {
    std::lock_guard<std::mutex> lock(mtx_);
    return total_alertas_;
}
