#pragma once
#include <queue>
#include <mutex>
#include <condition_variable>
#include <optional>
#include "MetricaSensor.hpp"

// Cola concurrente (BlockingQueue) — el recurso compartido entre los hilos
// productores (sensores) y el pool de hilos consumidores.
//
// Por qué mutex + 2 condition_variable y no solo un mutex:
//  - El mutex por sí solo evita la corrupción de datos (condición de carrera),
//    pero si un consumidor necesita esperar a que haya datos tendría que
//    sondear en un bucle (busy-waiting), desperdiciando CPU.
//  - cv_consumidores_ bloquea a los consumidores sin gastar ciclos cuando la
//    cola está vacía, y los despierta justo cuando push() agrega un dato.
//  - cv_productores_ bloquea a los productores cuando la cola llega a su
//    capacidad máxima (evita que una ráfaga de N sensores desborde la
//    memoria), y los despierta cuando pop() libera espacio.
class ColaConcurrente {
public:
    explicit ColaConcurrente(std::size_t capacidad_maxima = 1024)
        : capacidad_maxima_(capacidad_maxima) {}

    // Agrega un dato a la cola. Bloquea al hilo llamante si está llena.
    void push(MetricaSensor dato) {
        std::unique_lock<std::mutex> lock(mtx_);
        cv_productores_.wait(lock, [this] { return cerrada_ || buffer_.size() < capacidad_maxima_; });
        if (cerrada_) return;
        buffer_.push(std::move(dato));
        lock.unlock();
        cv_consumidores_.notify_one();
    }

    // Extrae un dato de la cola. Bloquea al hilo llamante si está vacía.
    // Devuelve std::nullopt solo cuando la cola fue cerrada (cerrar()) y ya
    // no quedan datos pendientes: es la señal de apagado ordenado para que
    // los hilos consumidores terminen su bucle sin perder lecturas.
    std::optional<MetricaSensor> pop() {
        std::unique_lock<std::mutex> lock(mtx_);
        cv_consumidores_.wait(lock, [this] { return cerrada_ || !buffer_.empty(); });
        if (buffer_.empty()) return std::nullopt;
        MetricaSensor dato = std::move(buffer_.front());
        buffer_.pop();
        lock.unlock();
        cv_productores_.notify_one();
        return dato;
    }

    // Marca la cola como cerrada: los productores dejan de poder insertar y
    // los consumidores bloqueados se despiertan para drenar lo que quede y
    // terminar. Se usa al finalizar la simulación/el programa.
    void cerrar() {
        {
            std::lock_guard<std::mutex> lock(mtx_);
            cerrada_ = true;
        }
        cv_consumidores_.notify_all();
        cv_productores_.notify_all();
    }

    std::size_t tamanio() const {
        std::lock_guard<std::mutex> lock(mtx_);
        return buffer_.size();
    }

private:
    mutable std::mutex mtx_;
    std::condition_variable cv_productores_;
    std::condition_variable cv_consumidores_;
    std::queue<MetricaSensor> buffer_;
    std::size_t capacidad_maxima_;
    bool cerrada_ = false;
};
