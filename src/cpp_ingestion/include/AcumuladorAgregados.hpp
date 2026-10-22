#pragma once
#include <mutex>
#include <unordered_map>
#include <string>

// Recurso compartido descrito en la sección 3.1 del Documento de
// Justificación: "múltiples hilos concurrentes... necesitan actualizar
// simultáneamente un mismo acumulador global en memoria que calcula el
// promedio de contaminación". Sin protección, dos hilos trabajadores podrían
// leer el mismo acumulado, sumarle su propio dato y escribir de vuelta,
// y una de las escrituras sobrescribiría (perdería) a la otra.
//
// Aquí se usa std::mutex por ser la opción de menor sobrecarga para una
// operación aritmética corta sobre una estructura simple (ver sección 3.2
// del Documento de Justificación, columna "Por qué ese mecanismo").
class AcumuladorAgregados {
public:
    struct Promedios {
        double pm25 = 0.0;
        double co2 = 0.0;
        double tmp = 0.0;
        long conteo = 0;
    };

    void registrar(const std::string& sensor_id, double pm25, double co2, double tmp) {
        std::lock_guard<std::mutex> lock(mtx_);
        Acc& acc = por_sensor_[sensor_id];
        acc.suma_pm25 += pm25;
        acc.suma_co2 += co2;
        acc.suma_tmp += tmp;
        acc.conteo += 1;
    }

    Promedios promediosDe(const std::string& sensor_id) const {
        std::lock_guard<std::mutex> lock(mtx_);
        auto it = por_sensor_.find(sensor_id);
        if (it == por_sensor_.end() || it->second.conteo == 0) return {};
        const Acc& acc = it->second;
        return Promedios{acc.suma_pm25 / acc.conteo, acc.suma_co2 / acc.conteo,
                          acc.suma_tmp / acc.conteo, acc.conteo};
    }

    long conteoTotal() const {
        std::lock_guard<std::mutex> lock(mtx_);
        long total = 0;
        for (const auto& par : por_sensor_) total += par.second.conteo;
        return total;
    }

private:
    struct Acc {
        double suma_pm25 = 0.0;
        double suma_co2 = 0.0;
        double suma_tmp = 0.0;
        long conteo = 0;
    };

    mutable std::mutex mtx_;
    std::unordered_map<std::string, Acc> por_sensor_;
};
