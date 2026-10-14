#pragma once
#include <mutex>
#include <string>
#include <unordered_set>
#include "MetricaSensor.hpp"
#include "Alerta.hpp"

// Conexion real a la base de datos (MySQL 8, ver src/database/schema.sql),
// usando el conector C de MariaDB (ABI/protocolo compatible con MySQL;
// ver src/cpp_ingestion/README.md para como instalarlo).
//
// Cada "transaccion" (lectura + alerta, si aplica) se ejecuta con
// START TRANSACTION / COMMIT real y protegida por mutex, porque el handle
// de conexion no es seguro para usarse desde varios hilos al mismo tiempo:
// todos los hilos trabajadores del ThreadPoolConsumidor comparten una sola
// instancia de DatabaseManager (y por lo tanto una sola conexion),
// serializada aqui, igual que describe la seccion 3.2 del Documento de
// Justificacion para el recurso compartido "buffer de datos".
class DatabaseManager {
public:
    struct Config {
        std::string host = "127.0.0.1";
        unsigned int puerto = 3306;
        std::string usuario = "root";
        std::string password;              // normalmente viene de la variable de entorno MYSQL_PASSWORD
        std::string base_datos = "monitoreo_ambiental";
    };

    explicit DatabaseManager(const Config& config);
    ~DatabaseManager();

    DatabaseManager(const DatabaseManager&) = delete;
    DatabaseManager& operator=(const DatabaseManager&) = delete;

    // Guarda la lectura y, si se recibe una alerta, la guarda en la MISMA
    // transaccion real (START TRANSACTION ... COMMIT / ROLLBACK). Registra
    // automaticamente el sensor en la tabla `sensores` la primera vez que se
    // ve su sensor_id (INSERT IGNORE), para no romper la FK de `lecturas`.
    // Devuelve false ante error de BD; los duplicados (mismo sensor_id +
    // timestamp, error 1062) se consideran "manejados" y no se cuentan como
    // error fatal, solo se omiten (igual que carga_concurrente.py).
    bool guardarLecturaTransaccional(const MetricaSensor& dato, const Alerta* alerta_opcional);

    long totalLecturasGuardadas() const;
    long totalAlertasGuardadas() const;
    long totalDuplicadosRechazados() const;

private:
    bool ejecutar(const std::string& sql);
    void asegurarSensorRegistrado(const std::string& sensor_id);
    static std::string timestampIso8601AFechaMysql(const std::string& iso8601);

    mutable std::mutex mtx_;
    // Se guarda como void* (en vez de MYSQL*) para no obligar a que este
    // header tenga el include path del conector configurado; se convierte
    // de vuelta a MYSQL* dentro de DatabaseManager.cpp, que es el unico
    // archivo que incluye <mysql.h>.
    void* conexion_ = nullptr;
    std::unordered_set<std::string> sensores_registrados_;
    long total_lecturas_ = 0;
    long total_alertas_ = 0;
    long total_duplicados_ = 0;
};
