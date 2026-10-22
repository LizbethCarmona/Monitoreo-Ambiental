#include "DatabaseManager.hpp"
#include <mysql.h>
#include <mysqld_error.h>
#include <stdexcept>
#include <sstream>
#include <vector>
#include <cstring>
#include <cstdlib>
#include <cmath>

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
    if (mysql_query(conn, "SET time_zone = '+00:00'") != 0) {
        std::string error = mysql_error(conn);
        mysql_close(conn);
        throw std::runtime_error("DatabaseManager: no se pudo fijar la zona horaria UTC: " + error);
    }
    if (mysql_autocommit(conn, 0) != 0) {
        std::string error = mysql_error(conn);
        mysql_close(conn);
        throw std::runtime_error("DatabaseManager: no se pudo habilitar el control transaccional: " + error);
    }
    conexion_ = conn;
}

DatabaseManager::~DatabaseManager() {
    if (conexion_) {
        mysql_close(comoMysql(conexion_));
    }
}

bool DatabaseManager::ejecutar(const std::string& sql) {
    MYSQL* conn = comoMysql(conexion_);
    if (mysql_query(conn, sql.c_str()) == 0) return true;
    ultimo_error_ = mysql_error(conn);
    return false;
}

bool DatabaseManager::asegurarSensorRegistrado(const std::string& sensor_id) {
    // Cache local para no reenviar el mismo INSERT IGNORE en cada lectura:
    // solo se registra una vez por sensor_id durante la vida del proceso.
    if (sensores_registrados_.count(sensor_id) > 0) return true;

    MYSQL* conn = comoMysql(conexion_);
    std::string id_escapado = escapar(conn, sensor_id);
    std::ostringstream sql;
    sql << "INSERT IGNORE INTO sensores (sensor_id, nombre) VALUES ('"
        << id_escapado << "', '" << id_escapado << "')";
    if (!ejecutar(sql.str())) return false;
    sensores_registrados_.insert(sensor_id);
    return true;
}

UmbralesLectura DatabaseManager::cargarUmbralesLectura() {
    std::lock_guard<std::mutex> lock(mtx_);
    MYSQL* conn = comoMysql(conexion_);
    if (!ejecutar("SELECT metrica, nivel, valor_limite FROM umbrales WHERE aplica_a = 'lectura'")) {
        throw std::runtime_error("No se pudieron cargar los umbrales de lectura: " + ultimo_error_);
    }
    MYSQL_RES* resultado = mysql_store_result(conn);
    if (!resultado) {
        ultimo_error_ = mysql_error(conn);
        throw std::runtime_error("No se pudieron leer los umbrales de lectura: " + ultimo_error_);
    }

    UmbralesLectura umbrales;
    MYSQL_ROW fila;
    while ((fila = mysql_fetch_row(resultado)) != nullptr) {
        if (!fila[0] || !fila[1] || !fila[2]) continue;
        char* fin = nullptr;
        double limite = std::strtod(fila[2], &fin);
        if (fin == fila[2] || *fin != '\0' || !std::isfinite(limite)) {
            mysql_free_result(resultado);
            throw std::runtime_error("Valor no numerico en la tabla umbrales.");
        }
        umbrales[fila[0]][fila[1]] = limite;
    }
    mysql_free_result(resultado);
    for (const char* metrica : {"pm25", "co2", "tmp"}) {
        auto por_metrica = umbrales.find(metrica);
        if (por_metrica == umbrales.end() || por_metrica->second.count("critico") == 0) {
            throw std::runtime_error(std::string("Falta el umbral critico de lectura para ") + metrica + ".");
        }
    }
    return umbrales;
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

    if (!asegurarSensorRegistrado(dato.sensor_id)) {
        ejecutar("ROLLBACK");
        return false;
    }

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
    }

    if (!ejecutar("COMMIT")) {
        ejecutar("ROLLBACK");
        return false;
    }
    ++total_lecturas_;
    if (alerta_opcional != nullptr) ++total_alertas_;
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

std::string DatabaseManager::ultimoError() const {
    std::lock_guard<std::mutex> lock(mtx_);
    return ultimo_error_;
}
