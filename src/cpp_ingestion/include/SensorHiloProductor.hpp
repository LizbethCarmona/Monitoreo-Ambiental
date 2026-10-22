#pragma once
#include <string>
#include <atomic>
#include "ColaConcurrente.hpp"

// Simula un nodo sensor IoT y genera lecturas sintéticas para desarrollar y
// probar el núcleo concurrente sin depender de hardware ni de un broker.
// Cada instancia corre en su propio std::thread (uno por sensor) y tiene su
// propio generador de números aleatorios, por lo que no comparte estado con
// otros productores: el único punto de contacto entre hilos es la
// ColaConcurrente recibida por referencia.
class SensorHiloProductor {
public:
    // Si num_lecturas <= 0, el sensor genera lecturas indefinidamente (modo
    // continuo, para alimentar la base de datos en "tiempo real") hasta que
    // detener_ se ponga en true (por ejemplo, al recibir Ctrl+C en main.cpp).
    SensorHiloProductor(std::string sensor_id, ColaConcurrente& cola, int num_lecturas,
                        int intervalo_ms, unsigned semilla,
                        std::atomic<bool>& detener);

    // Bucle principal que corre en el hilo del productor.
    void simularLecturas();

    void enviarACola(MetricaSensor dato);

private:
    std::string sensor_id_;
    ColaConcurrente& cola_;
    int num_lecturas_;
    int intervalo_ms_;
    unsigned semilla_;
    std::atomic<bool>& detener_;
};
