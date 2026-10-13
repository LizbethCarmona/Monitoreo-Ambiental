// Demo del núcleo concurrente — Monitoreo ambiental en tiempo real
//
// Lanza N hilos productores (uno por sensor simulado), un pool de hilos
// consumidores que calculan agregados y evalúan umbrales, y una capa de
// persistencia transaccional (ver DatabaseManager). Al final verifica que
// el total de lecturas procesadas coincide EXACTAMENTE con el total
// generado por los productores: si no coincidiera, sería evidencia de una
// condición de carrera (datos perdidos en la cola o en el acumulador).
#include <iostream>
#include <vector>
#include <thread>
#include <string>

#include "MetricaSensor.hpp"
#include "ColaConcurrente.hpp"
#include "SensorHiloProductor.hpp"
#include "ThreadPoolConsumidor.hpp"
#include "DatabaseManager.hpp"

int main(int argc, char** argv) {
    int num_sensores = 6;
    int lecturas_por_sensor = 50;
    int num_workers = 4;
    int intervalo_ms = 5;

    if (argc >= 2) num_sensores = std::stoi(argv[1]);
    if (argc >= 3) lecturas_por_sensor = std::stoi(argv[2]);
    if (argc >= 4) num_workers = std::stoi(argv[3]);

    std::cout << "=== Monitoreo ambiental en tiempo real - nucleo concurrente ===\n";
    std::cout << "Sensores (hilos productores): " << num_sensores << "\n";
    std::cout << "Lecturas por sensor:          " << lecturas_por_sensor << "\n";
    std::cout << "Hilos trabajadores (pool):    " << num_workers << "\n\n";

    ColaConcurrente cola(/*capacidad_maxima=*/256);
    DatabaseManager db("."); // escribe lecturas.log / alertas.log en el directorio actual

    ThreadPoolConsumidor pool(num_workers, cola, db);
    pool.iniciar();

    std::vector<std::thread> productores;
    std::vector<SensorHiloProductor> sensores;
    sensores.reserve(num_sensores);
    for (int i = 0; i < num_sensores; ++i) {
        std::string id = "sensor_" + (i + 1 < 10 ? std::string("0") : std::string("")) + std::to_string(i + 1);
        sensores.emplace_back(id, 1883, cola, lecturas_por_sensor, intervalo_ms, /*semilla=*/1000u + i);
    }
    for (auto& sensor : sensores) {
        productores.emplace_back(&SensorHiloProductor::recibirLecturasMQTT, &sensor);
    }

    for (auto& hilo : productores) hilo.join();  // esperar a que todos los sensores terminen de producir
    cola.cerrar();                                // ya no llegarán más datos: apagado ordenado
    pool.esperarFinalizacion();                    // esperar a que el pool drene la cola por completo

    long total_esperado = static_cast<long>(num_sensores) * lecturas_por_sensor;
    long total_procesado = pool.totalProcesadas();

    std::cout << "Lecturas generadas:   " << total_esperado << "\n";
    std::cout << "Lecturas procesadas:  " << total_procesado << "\n";
    std::cout << "Lecturas guardadas:   " << db.totalLecturasGuardadas() << "\n";
    std::cout << "Alertas generadas:    " << pool.totalAlertas() << "\n";

    bool integridad_ok = (total_procesado == total_esperado) &&
                         (db.totalLecturasGuardadas() == total_esperado);

    std::cout << "\nIntegridad (sin perdida de datos): " << (integridad_ok ? "OK" : "FALLO") << "\n";

    for (int i = 0; i < num_sensores; ++i) {
        std::string id = "sensor_" + (i + 1 < 10 ? std::string("0") : std::string("")) + std::to_string(i + 1);
        auto prom = pool.agregados().promediosDe(id);
        if (prom.conteo > 0) {
            std::cout << "  " << id << ": pm2.5=" << prom.pm25 << " co2=" << prom.co2
                      << " tmp=" << prom.tmp << " (n=" << prom.conteo << ")\n";
        }
    }

    return integridad_ok ? 0 : 1;
}
