#pragma once
#include <vector>
#include <thread>
#include <atomic>
#include "ColaConcurrente.hpp"
#include "AcumuladorAgregados.hpp"
#include "DatabaseManager.hpp"

// Pool de hilos trabajadores que consume de la ColaConcurrente, calcula
// agregados en paralelo y evalúa umbrales de contaminación (ver UML:
// ThreadPoolConsumidor). Cada trabajador procesa una métrica a la vez de
// forma independiente; el único recurso que comparten entre sí es el
// AcumuladorAgregados (protegido con mutex) y el DatabaseManager (también
// protegido con mutex internamente).
class ThreadPoolConsumidor {
public:
    ThreadPoolConsumidor(int num_workers, ColaConcurrente& cola, DatabaseManager& db);

    void iniciar();                 // lanza num_workers_ hilos trabajadores
    void esperarFinalizacion();     // join() de todos los trabajadores

    long totalProcesadas() const { return total_procesadas_.load(); }
    long totalAlertas() const { return total_alertas_.load(); }
    const AcumuladorAgregados& agregados() const { return agregados_; }

private:
    void procesarMetricas();                                   // bucle de cada trabajador
    void calcularPromediosParalelo(const MetricaSensor& dato);  // actualiza el acumulador compartido
    bool evaluarUmbrales(const MetricaSensor& dato, Alerta& salida) const; // true si hay alerta

    int num_workers_;
    ColaConcurrente& cola_;
    DatabaseManager& db_;
    std::vector<std::thread> trabajadores_;
    AcumuladorAgregados agregados_;
    std::atomic<long> total_procesadas_{0};
    std::atomic<long> total_alertas_{0};
};
