// Prueba de carga del patron productor-consumidor (cola + pool de hilos)
// fuera del flujo de persistencia, para aislar la ColaConcurrente y el
// ThreadPoolConsumidor de la base de datos. Usa una capacidad pequeña a
// proposito para forzar que productores Y consumidores se bloqueen entre si
// repetidamente (caso mas dificil para el mutex/condition_variable).
#include <iostream>
#include <thread>
#include <vector>
#include <atomic>

#include "ColaConcurrente.hpp"

int main() {
    constexpr int NUM_PRODUCTORES = 15;
    constexpr int ITEMS_POR_PRODUCTOR = 2000;
    constexpr int NUM_CONSUMIDORES = 5;
    constexpr std::size_t CAPACIDAD_COLA = 8; // pequena a proposito: fuerza bloqueo en ambos sentidos

    ColaConcurrente cola(CAPACIDAD_COLA);
    std::atomic<long> total_consumido{0};

    std::vector<std::thread> productores;
    for (int p = 0; p < NUM_PRODUCTORES; ++p) {
        productores.emplace_back([&cola, p]() {
            for (int i = 0; i < ITEMS_POR_PRODUCTOR; ++i) {
                MetricaSensor dato;
                dato.sensor_id = "sensor_" + std::to_string(p);
                dato.pm2_5 = i;
                cola.push(dato);
            }
        });
    }

    std::vector<std::thread> consumidores;
    for (int c = 0; c < NUM_CONSUMIDORES; ++c) {
        consumidores.emplace_back([&cola, &total_consumido]() {
            while (auto dato = cola.pop()) {
                total_consumido.fetch_add(1, std::memory_order_relaxed);
            }
        });
    }

    for (auto& h : productores) h.join();
    cola.cerrar();
    for (auto& h : consumidores) h.join();

    long esperado = static_cast<long>(NUM_PRODUCTORES) * ITEMS_POR_PRODUCTOR;
    std::cout << "=== Prueba de carga: ColaConcurrente + pool ===\n";
    std::cout << "Items esperados:  " << esperado << "\n";
    std::cout << "Items consumidos: " << total_consumido.load() << "\n";
    bool ok = (total_consumido.load() == esperado);
    std::cout << (ok ? "OK: ningun dato perdido/duplicado\n" : "FALLO: hay discrepancia\n");
    return ok ? 0 : 1;
}
