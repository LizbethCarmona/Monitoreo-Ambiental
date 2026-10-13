#pragma once
#include <mutex>
#include <fstream>
#include <string>
#include "MetricaSensor.hpp"
#include "Alerta.hpp"

// Fase 1 (Sprint 1-2, núcleo concurrente): todavía NO se conecta un cliente
// real de MySQL desde C++; esa integración corresponde a la Semana 4 del
// cronograma ("conectar consumidores con la capa de persistencia"). El
// esquema real de la base de datos ya existe en src/database/schema.sql y el
// equipo de base de datos ya validó la carga concurrente con
// src/database/carga_concurrente.py.
//
// Esta clase ofrece la MISMA garantía que tendrá la versión con MySQL: cada
// "transacción" (una lectura y, si corresponde, su alerta) se escribe de
// forma atómica y protegida por mutex, de modo que dos hilos consumidores
// escribiendo al mismo tiempo nunca intercalen ni corrompan un registro.
// Mientras se integra MySQL, persiste en archivos de texto a modo de bitácora.
class DatabaseManager {
public:
    explicit DatabaseManager(const std::string& directorio_salida = ".");

    // Guarda la lectura y, si se recibe una alerta, la guarda en la MISMA
    // "transacción" (ambas escrituras ocurren bajo el mismo lock_guard).
    // Devuelve false si no se pudo escribir en el destino de persistencia.
    bool guardarLecturaTransaccional(const MetricaSensor& dato, const Alerta* alerta_opcional);

    long totalLecturasGuardadas() const;
    long totalAlertasGuardadas() const;

private:
    mutable std::mutex mtx_;
    std::ofstream lecturas_log_;
    std::ofstream alertas_log_;
    long total_lecturas_ = 0;
    long total_alertas_ = 0;
};
