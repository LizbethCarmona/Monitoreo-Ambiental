#pragma once

// Límites por métrica, tomados de src/database/schema.sql (tabla `umbrales`),
// que a su vez documenta su fuente normativa:
//   PM2.5 -> NOM-025-SSA1-2021 (valores de lectura puntual son PROVISIONALES,
//            la norma solo fija el promedio de 24 h)
//   CO2   -> NOM-010-STPS-2014 (VLE-PPT promedio 8 h, VLE-CT 15 min)
//   Temp  -> NOM-015-STPS-2001 (Tabla 1, régimen ligero 100% exposición)
// Mantener esta tabla sincronizada con src/database/schema.sql si el equipo
// de base de datos ajusta algún valor.
namespace umbrales {
    constexpr double PM25_ADVERTENCIA = 35.0;
    constexpr double PM25_CRITICO     = 75.0;
    constexpr double CO2_ADVERTENCIA  = 2500.0;
    constexpr double CO2_CRITICO      = 30000.0;
    constexpr double TMP_ADVERTENCIA  = 30.0;
    constexpr double TMP_CRITICO      = 32.2;
}
