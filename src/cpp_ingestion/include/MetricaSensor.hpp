#pragma once
#include <string>
#include <sstream>

// Representa una lectura individual de un sensor ambiental.
// Coincide con el esquema definido en docs/metricas_schema.json y con la
// clase MetricaSensor del diagrama UML (docs/uml/diagrama_clases.puml).
struct MetricaSensor {
    std::string sensor_id;
    double pm2_5 = 0.0;   // ug/m3
    double co2 = 0.0;     // ppm
    double tmp = 0.0;     // grados Celsius
    std::string timestamp; // ISO 8601 UTC

    std::string toJson() const {
        std::ostringstream oss;
        oss << "{"
            << "\"sensor_id\":\"" << sensor_id << "\","
            << "\"pm2.5\":" << pm2_5 << ","
            << "\"co2\":" << co2 << ","
            << "\"tmp\":" << tmp << ","
            << "\"timestamp\":\"" << timestamp << "\""
            << "}";
        return oss.str();
    }
};
