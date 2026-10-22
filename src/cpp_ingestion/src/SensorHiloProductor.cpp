#include "SensorHiloProductor.hpp"
#include <chrono>
#include <thread>
#include <random>
#include <sstream>
#include <iomanip>

SensorHiloProductor::SensorHiloProductor(std::string sensor_id, ColaConcurrente& cola,
                                         int num_lecturas, int intervalo_ms, unsigned semilla,
                                         std::atomic<bool>& detener)
    : sensor_id_(std::move(sensor_id)), cola_(cola),
      num_lecturas_(num_lecturas), intervalo_ms_(intervalo_ms), semilla_(semilla), detener_(detener) {}

namespace {
std::string marcaTemporalUtcIso8601() {
    using namespace std::chrono;
    auto ahora = system_clock::now();
    auto ms = duration_cast<milliseconds>(ahora.time_since_epoch()) % 1000;
    std::time_t tiempo_c = system_clock::to_time_t(ahora);
    std::tm tm_utc{};
#if defined(_WIN32)
    gmtime_s(&tm_utc, &tiempo_c);
#else
    gmtime_r(&tiempo_c, &tm_utc);
#endif
    std::ostringstream oss;
    oss << std::put_time(&tm_utc, "%Y-%m-%dT%H:%M:%S")
        << '.' << std::setfill('0') << std::setw(3) << ms.count() << 'Z';
    return oss.str();
}
} // namespace

void SensorHiloProductor::simularLecturas() {
    // Generador de números aleatorios propio del hilo (no se comparte entre
    // productores), evitando así otra posible condición de carrera: dos
    // hilos usando el mismo std::mt19937 al mismo tiempo.
    std::mt19937 rng(semilla_);
    std::uniform_real_distribution<double> dist_pm25(5.0, 55.0);
    std::uniform_real_distribution<double> dist_co2(380.0, 1200.0);
    std::uniform_real_distribution<double> dist_tmp(15.0, 33.0);
    std::uniform_real_distribution<double> prob_pico(0.0, 1.0);

    // Modo finito: for de num_lecturas_ iteraciones. Modo continuo
    // (num_lecturas_ <= 0): sigue generando lecturas hasta que detener_ se
    // ponga en true (ver manejo de SIGINT en main.cpp).
    for (int i = 0; num_lecturas_ <= 0 || i < num_lecturas_; ++i) {
        if (detener_.load(std::memory_order_relaxed)) break;

        MetricaSensor dato;
        dato.sensor_id = sensor_id_;
        dato.pm2_5 = dist_pm25(rng);
        dato.co2 = dist_co2(rng);
        dato.tmp = dist_tmp(rng);

        // ~8% de probabilidad de un pico de contaminación, para poder
        // demostrar en la demo que el motor de alertas sí dispara cuando se
        // supera un umbral crítico (ver Umbrales.hpp).
        if (prob_pico(rng) < 0.08) {
            dato.pm2_5 = 75.0 + dist_pm25(rng);
        }

        dato.timestamp = marcaTemporalUtcIso8601();
        enviarACola(std::move(dato));

        if (intervalo_ms_ > 0) {
            std::this_thread::sleep_for(std::chrono::milliseconds(intervalo_ms_));
        }
    }
}

void SensorHiloProductor::enviarACola(MetricaSensor dato) {
    cola_.push(std::move(dato));
}
