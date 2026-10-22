#pragma once

#include <map>
#include <string>

// Los límites provienen de `umbrales` en src/database/schema.sql y se cargan
// al arrancar. Solo se incluyen aquí los aplicables a una lectura puntual.
using UmbralesLectura = std::map<std::string, std::map<std::string, double>>;
