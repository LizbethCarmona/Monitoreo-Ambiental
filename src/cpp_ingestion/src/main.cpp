// Nucleo concurrente — Monitoreo ambiental en tiempo real
//
// Lanza N hilos productores (uno por sensor simulado), un pool de hilos
// consumidores que calculan agregados y evalúan umbrales, y los persiste de
// forma transaccional en MySQL real (ver DatabaseManager).
//
// Uso:
//   bin/demo [num_sensores] [lecturas_por_sensor] [num_workers] [intervalo_ms]
//
// Si lecturas_por_sensor es 0 (o se omite), corre en MODO CONTINUO: genera
// lecturas sinteticas indefinidamente y las persiste en MySQL hasta Ctrl+C.
//
// Variables de entorno para la conexion a MySQL (mismas que
// src/database/carga_concurrente.py): MYSQL_HOST, MYSQL_PORT, MYSQL_USER,
// MYSQL_PASSWORD (obligatoria), MYSQL_DATABASE.
#include <iostream>
#include <vector>
#include <thread>
#include <string>
#include <chrono>
#include <csignal>
#include <cstdlib>
#include <atomic>

#include "MetricaSensor.hpp"
#include "ColaConcurrente.hpp"
#include "SensorHiloProductor.hpp"
#include "ThreadPoolConsumidor.hpp"
#include "DatabaseManager.hpp"

namespace {
std::atomic<bool> g_detener{false};

void manejarSigint(int) {
    g_detener.store(true, std::memory_order_relaxed);
}

std::string env_o(const char* nombre, const std::string& valor_por_defecto) {
    const char* v = std::getenv(nombre);
    return v ? std::string(v) : valor_por_defecto;
}

std::string idSensor(int indice) {
    return "sensor_" + (indice + 1 < 10 ? std::string("0") : std::string("")) + std::to_string(indice + 1);
}
} // namespace

int main(int argc, char** argv) {
    int num_sensores = 6;
    int lecturas_por_sensor = 0;   // 0 = modo continuo
    int num_workers = 4;
    int intervalo_ms = 2000;

    if (argc >= 2) num_sensores = std::stoi(argv[1]);
    if (argc >= 3) lecturas_por_sensor = std::stoi(argv[2]);
    if (argc >= 4) num_workers = std::stoi(argv[3]);
    if (argc >= 5) intervalo_ms = std::stoi(argv[4]);

    std::signal(SIGINT, manejarSigint);

    DatabaseManager::Config db_config;
    db_config.host = env_o("MYSQL_HOST", "127.0.0.1");
    db_config.puerto = static_cast<unsigned int>(std::stoi(env_o("MYSQL_PORT", "3306")));
    db_config.usuario = env_o("MYSQL_USER", "root");
    db_config.password = env_o("MYSQL_PASSWORD", "");
    db_config.base_datos = env_o("MYSQL_DATABASE", "monitoreo_ambiental");

    if (db_config.password.empty()) {
        std::cerr << "Falta la variable de entorno MYSQL_PASSWORD. En PowerShell:\n"
                  << "  $env:MYSQL_PASSWORD = 'tu_clave'\n";
        return 2;
    }

    std::cout << "=== Monitoreo ambiental en tiempo real - nucleo concurrente ===\n";
    std::cout << "Sensores (hilos productores): " << num_sensores << "\n";
    std::cout << "Hilos trabajadores (pool):    " << num_workers << "\n";
    std::cout << "Intervalo por lectura:        " << intervalo_ms << " ms\n";
    if (lecturas_por_sensor <= 0) {
        std::cout << "Modo: CONTINUO (Ctrl+C para detener)\n";
    } else {
        std::cout << "Lecturas por sensor:          " << lecturas_por_sensor << "\n";
    }
    std::cout << "MySQL: " << db_config.usuario << "@" << db_config.host << ":" << db_config.puerto
              << "/" << db_config.base_datos << "\n\n";

    DatabaseManager db(db_config);
    std::cout << "Conexion a MySQL establecida.\n\n";

    ColaConcurrente cola(/*capacidad_maxima=*/256);
    ThreadPoolConsumidor pool(num_workers, cola, db);
    pool.iniciar();

    std::vector<std::thread> productores;
    std::vector<SensorHiloProductor> sensores;
    sensores.reserve(num_sensores);
    for (int i = 0; i < num_sensores; ++i) {
        sensores.emplace_back(idSensor(i), cola, lecturas_por_sensor, intervalo_ms,
                              /*semilla=*/1000u + i, g_detener);
    }
    for (auto& sensor : sensores) {
        productores.emplace_back(&SensorHiloProductor::simularLecturas, &sensor);
    }

    // Hilo monitor: en modo continuo muestra el avance de la simulacion y la persistencia.
    std::thread monitor([&]() {
        while (!g_detener.load(std::memory_order_relaxed)) {
            std::this_thread::sleep_for(std::chrono::seconds(5));
            if (g_detener.load(std::memory_order_relaxed)) break;
            std::cout << "[monitor] procesadas=" << pool.totalProcesadas()
                      << " guardadas=" << db.totalLecturasGuardadas()
                      << " alertas=" << pool.totalAlertas()
                      << " errores_persistencia=" << pool.totalErroresPersistencia()
                      << " duplicados=" << db.totalDuplicadosRechazados() << std::endl;
        }
    });

    for (auto& hilo : productores) hilo.join();  // esperar a que todos los sensores terminen de producir
    g_detener.store(true, std::memory_order_relaxed);
    cola.cerrar();                                // ya no llegarán más datos: apagado ordenado
    pool.esperarFinalizacion();                    // esperar a que el pool drene la cola por completo
    monitor.join();

    long total_esperado = static_cast<long>(num_sensores) * lecturas_por_sensor; // solo valido en modo finito
    long total_procesado = pool.totalProcesadas();

    std::cout << "\n--- Resumen final ---\n";
    std::cout << "Lecturas procesadas:   " << total_procesado << "\n";
    std::cout << "Lecturas guardadas:    " << db.totalLecturasGuardadas() << "\n";
    std::cout << "Duplicados rechazados: " << db.totalDuplicadosRechazados() << "\n";
    std::cout << "Errores de persistencia: " << pool.totalErroresPersistencia() << "\n";
    std::cout << "Alertas generadas:     " << pool.totalAlertas() << "\n";

    bool integridad_ok =
        (db.totalLecturasGuardadas() + db.totalDuplicadosRechazados()) == total_procesado
        && pool.totalErroresPersistencia() == 0;
    if (lecturas_por_sensor > 0) {
        integridad_ok = integridad_ok && (total_procesado + pool.totalErroresPersistencia() == total_esperado);
        std::cout << "Lecturas generadas:    " << total_esperado << "\n";
    }
    std::cout << "\nIntegridad (sin perdida de datos): " << (integridad_ok ? "OK" : "FALLO") << "\n";

    for (int i = 0; i < num_sensores; ++i) {
        std::string id = idSensor(i);
        auto prom = pool.agregados().promediosDe(id);
        if (prom.conteo > 0) {
            std::cout << "  " << id << ": pm2.5=" << prom.pm25 << " co2=" << prom.co2
                      << " tmp=" << prom.tmp << " (n=" << prom.conteo << ")\n";
        }
    }

    return integridad_ok ? 0 : 1;
}
