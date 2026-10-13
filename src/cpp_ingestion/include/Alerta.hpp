#pragma once
#include <string>

// Evento generado por ThreadPoolConsumidor cuando una métrica supera un
// umbral (ver Umbrales.hpp). Se persiste junto con su lectura de origen en
// la misma transacción (ver DatabaseManager::guardarLecturaTransaccional).
struct Alerta {
    std::string sensor_id;
    std::string metrica;  // "pm25" | "co2" | "tmp"
    std::string nivel;    // "advertencia" | "critico"
    double valor_medido = 0.0;
    double valor_limite = 0.0;
    std::string mensaje;
};
