#include "DatabaseManager.hpp"
#include <mysql.h>
#include <mysqld_error.h>
#include <stdexcept>
#include <sstream>
#include <vector>
#include <cstring>

namespace {
MYSQL* comoMysql(void* ptr) { return static_cast<MYSQL*>(ptr); }

// Escapa un valor de texto para incrustarlo de forma segura en una consulta
// SQL (evita inyeccion si algun dato de sensor llegara a tener comillas).
std::string escapar(MYSQL* conn, const std::string& valor) {
    std::vector<char> buffer(valor.size() * 2 + 1);
    unsigned long n = mysql_real_escape_string(conn, buffer.data(), valor.c_str(), valor.size());
    return std::string(buffer.data(), n);
}
} // namespace

DatabaseManager::DatabaseManager(const Config& config) {
    MYSQL* conn = mysql_init(nullptr);
    if (!conn) {
        throw std::runtime_error("DatabaseManager: mysql_init fallo (sin memoria)");
    }

    // autocommit se maneja manualmente (ver guardarLecturaTransaccional):
    // se necesita START TRANSACTION real para que lectura + alerta se
    // confirmen o se reviertan juntas.
    if (!mysql_real_connect(conn, config.host.c_str(), config.usuario.c_str(),
                            config.password.c_str(), config.base_datos.c_str(),
                            config.puerto, nullptr, 0)) {
        std::string error = mysql_error(conn);
        mysql_close(conn);
        throw std::runtime_error("DatabaseManager: no se pudo conectar a MySQL (" +
                                  config.host + ":" + std::to_string(config.puerto) + "): " + error);
    }
    mysql_autocommit(conn, 0);
    conexion_ = conn;
}

DatabaseManager::~DatabaseManager() {
    if (conexion_) {
        mysql_close(comoMysql(conexion_));
    }
}

bool DatabaseManager::ejecutar(const std::string& sql) {
    MYSQL* conn = comoMysql(conexion_);
    return mysql_query(conn, sql.c_str()) == 0;
}

void DatabaseManager::asegurarSensorRegistrado(const std::string& sensor_id) {
    // Cache local para no reenviar el mismo INSERT IGNORE en cada lectura:
    // solo se registra una vez por sensor_id durante la vida del proceso.
    if (sensores_registrados_.count(sensor_id) > 0) return;

    MYSQL* conn = comoMysql(conexion_);
    std::string id_escapado = escapar(conn, sensor_id);
    std::ostringstream sql;
    sql << "INSERT IGNORE INTO sensores (sensor_id, nombre) VALUES ('"
        << id_escapado << "', '" << id_escapado << "')";
    ejecutar(sql.str()); // si falla, el INSERT de la lectura fallara despues por la FK y se reportara ahi
    sensores_registrados_.insert(sensor_id);
}

std::string DatabaseManager::timestampIso8601AFechaMysql(const std::string& iso8601) {
    // Convierte "2026-10-14T00:12:34.567Z" -> "2026-10-14 00:12:34.567"
    // (formato que esperan las columnas DATETIME(3) del esquema).
    std::string resultado = iso8601;
    for (char& c : resultado) {
        if (c == 'T') c = ' ';
    }
    if (!resultado.empty() && resultado.back() == 'Z') {
        resultado.pop_back();
    }
    return resultado;
}

bool DatabaseManager::guardarLecturaTransaccional(const MetricaSensor& dato, const Alerta* alerta_opcional) {
    // Todo el bloque (registrar sensor si falta, insertar lectura, insertar
    // alerta) ocurre bajo un unico lock Y dentro de una unica transaccion de
    // MySQL: o se confirman todas las escrituras (COMMIT) o ninguna
    // (ROLLBACK), igual que exige la seccion 8 (Definition of Done) del
    // Documento de Justificacion ("toda escritura mantiene la atomicidad").
    std::lock_guard<std::mutex> lock(mtx_);
    MYSQL* conn = comoMysql(conexion_);

    asegurarSensorRegistrado(dato.sensor_id);

    if (!ejecutar("START TRANSACTION")) {
        return false;
    }

    std::string sensor_esc = escapar(conn, dato.sensor_id);
    std::string ts_mysql = escapar(conn, timestampIso8601AFechaMysql(dato.timestamp));

    std::ostringstream insert_lectura;
    insert_lectura << "INSERT INTO lecturas (sensor_id, pm25, co2, tmp, timestamp_lectura) VALUES ('"
                   << sensor_esc << "', " << dato.pm2_5 << ", " << dato.co2 << ", " << dato.tmp
                   << ", '" << ts_mysql << "')";

    if (!ejecutar(insert_lectura.str())) {
        unsigned int error_num = mysql_errno(conn);
        ejecutar("ROLLBACK");
        if (error_num == ER_DUP_ENTRY) {
            // Mismo sensor_id + timestamp_lectura ya existia (restriccion
            // UNIQUE KEY uq_sensor_momento): no es un error fatal, solo se
            // descarta el duplicado (igual que carga_concurrente.py).
            ++total_duplicados_;
            return true;
        }
        return false;
    }

    unsigned long long lectura_id = mysql_insert_id(conn);
    ++total_lecturas_;

    if (alerta_opcional != nullptr) {
        std::string metrica_esc = escapar(conn, alerta_opcional->metrica);
        std::string nivel_esc = escapar(conn, alerta_opcional->nivel);
        std::string mensaje_esc = escapar(conn, alerta_opcional->mensaje);

        std::ostringstream insert_alerta;
        insert_alerta << "INSERT INTO alertas (lectura_id, sensor_id, metrica, nivel, valor_medido, "
                      << "valor_limite, mensaje) VALUES (" << lectura_id << ", '" << sensor_esc << "', '"
                      << metrica_esc << "', '" << nivel_esc << "', " << alerta_opcional->valor_medido << ", "
                      << alerta_opcional->valor_limite << ", '" << mensaje_esc << "')";

        if (!ejecutar(insert_alerta.str())) {
            ejecutar("ROLLBACK");
            return false;
        }
        ++total_alertas_;
    }

    if (!ejecutar("COMMIT")) {
        return false;
    }
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

long DatabaseManager::totalDuplicadosRechazados() const {
    std::lock_guard<std::mutex> lock(mtx_);
    return total_duplicados_;
}
