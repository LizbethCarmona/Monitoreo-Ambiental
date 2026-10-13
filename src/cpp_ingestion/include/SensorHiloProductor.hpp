#pragma once
#include <string>
#include "ColaConcurrente.hpp"

// Simula un nodo sensor IoT. En producción, recibirLecturasMQTT() se
// conectaría a un broker MQTT (ver Sprint 3 "Redes" en el cronograma); por
// ahora genera lecturas sintéticas en rangos realistas para poder desarrollar
// y probar el núcleo concurrente sin depender de hardware ni de un broker.
// Cada instancia corre en su propio std::thread (uno por sensor) y tiene su
// propio generador de números aleatorios, por lo que no comparte estado con
// otros productores: el único punto de contacto entre hilos es la
// ColaConcurrente recibida por referencia.
class SensorHiloProductor {
public:
    SensorHiloProductor(std::string sensor_id, int puerto_mqtt, ColaConcurrente& cola,
                        int num_lecturas, int intervalo_ms, unsigned semilla);

    // Bucle principal que corre en el hilo del productor.
    void recibirLecturasMQTT();

    void enviarACola(MetricaSensor dato);

private:
    std::string sensor_id_;
    int puerto_mqtt_;
    ColaConcurrente& cola_;
    int num_lecturas_;
    int intervalo_ms_;
    unsigned semilla_;
};
