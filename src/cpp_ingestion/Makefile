# Makefile del nucleo concurrente (src/cpp_ingestion)
#
# Requiere un compilador con soporte completo de C++17 std::thread. En
# Windows, el MinGW.org clasico (p. ej. C:\MinGW) NO sirve porque su
# runtime no implementa <thread>/<mutex>; usar en su lugar un mingw-w64
# (MSYS2 ucrt64/mingw64) o compilar en Linux/WSL, que es donde el equipo
# planea correr el sistema finalmente.
#
# DatabaseManager se conecta a MySQL real usando el conector C de MariaDB
# (ABI/protocolo compatible con MySQL 8). Se detecta via pkg-config:
#   - Windows (MSYS2):  pacman -S mingw-w64-ucrt-x86_64-libmariadbclient \
#                               mingw-w64-ucrt-x86_64-pkgconf
#   - Linux (Debian/Ubuntu): apt install libmariadb-dev pkg-config
#
# Uso:
#   make            -> compila la demo (bin/demo) y las pruebas
#   make run-demo    -> compila y corre la demo del pipeline completo (requiere MySQL)
#   make test        -> compila y corre las dos pruebas de concurrencia (no requiere MySQL)
#   make clean       -> borra los binarios generados

CXX := g++
CXXFLAGS := -std=c++17 -Wall -Wextra -O2 -Iinclude
LDFLAGS := -pthread

# -fno-use-linker-plugin evita un bug de empaquetado conocido en algunas
# instalaciones de MSYS2/mingw-w64 en Windows (error "liblto_plugin.dll:
# error loading plugin"). No tiene efecto negativo en Linux.
CXXFLAGS += -fno-use-linker-plugin

MYSQL_CFLAGS := $(shell pkg-config --cflags libmariadb 2>/dev/null || pkg-config --cflags mariadb 2>/dev/null)
MYSQL_LIBS := $(shell pkg-config --libs libmariadb 2>/dev/null || pkg-config --libs mariadb 2>/dev/null)

BIN_DIR := bin
CORE_SRCS := src/SensorHiloProductor.cpp src/ThreadPoolConsumidor.cpp src/DatabaseManager.cpp

.PHONY: all run-demo run-continuo test clean

all: $(BIN_DIR)/demo $(BIN_DIR)/prueba_condicion_carrera $(BIN_DIR)/prueba_cola_concurrente

$(BIN_DIR):
	-mkdir $(BIN_DIR)

$(BIN_DIR)/demo: src/main.cpp $(CORE_SRCS) | $(BIN_DIR)
	$(CXX) $(CXXFLAGS) $(MYSQL_CFLAGS) -o $@ $^ $(LDFLAGS) $(MYSQL_LIBS)

$(BIN_DIR)/prueba_condicion_carrera: tests/prueba_condicion_carrera.cpp | $(BIN_DIR)
	$(CXX) $(CXXFLAGS) -o $@ $^ $(LDFLAGS)

$(BIN_DIR)/prueba_cola_concurrente: tests/prueba_cola_concurrente.cpp | $(BIN_DIR)
	$(CXX) $(CXXFLAGS) -o $@ $^ $(LDFLAGS)

run-demo: $(BIN_DIR)/demo
	./$(BIN_DIR)/demo

# Modo continuo: alimenta MySQL en tiempo real hasta Ctrl+C (ver main.cpp).
run-continuo: $(BIN_DIR)/demo
	./$(BIN_DIR)/demo 6 0 4 2000

test: $(BIN_DIR)/prueba_condicion_carrera $(BIN_DIR)/prueba_cola_concurrente
	./$(BIN_DIR)/prueba_condicion_carrera
	./$(BIN_DIR)/prueba_cola_concurrente

clean:
	rm -rf $(BIN_DIR) lecturas.log alertas.log
