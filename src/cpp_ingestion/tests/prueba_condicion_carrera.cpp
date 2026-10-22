// Reproduce, de forma medible, el escenario de condición de carrera descrito
// en la sección 3.1 del Documento de Justificación: múltiples hilos (uno por
// sensor) incrementan un mismo acumulador compartido. Se compara el
// acumulador SIN protección (con condición de carrera) contra el mismo
// acumulador CON mutex, usando el mismo patrón leer-sumar-escribir que
// describe el documento.
#include <iostream>
#include <thread>
#include <vector>
#include <mutex>

namespace {
constexpr int NUM_HILOS = 20;                 // N sensores concurrentes
constexpr int INCREMENTOS_POR_HILO = 20000;   // lecturas simuladas por sensor

long acumulador_inseguro = 0;
long acumulador_seguro = 0;
std::mutex mtx;

void incrementarInseguro() {
    for (int i = 0; i < INCREMENTOS_POR_HILO; ++i) {
        // Se separa deliberadamente leer/sumar/escribir en 3 pasos, con un
        // yield() en medio, para forzar el mismo entrelazado que describe la
        // seccion 3.1: "si el hilo del Sensor A y el hilo del Sensor B leen
        // el valor actual... y luego escriben... una escritura sobrescribe
        // a la otra". En un `acumulador_inseguro++` normal esta ventana de
        // riesgo existe igual, pero es tan corta que puede no manifestarse
        // de forma visible en cada corrida; el yield() la hace observable
        // de manera consistente para la demo.
        long leido = acumulador_inseguro;
        std::this_thread::yield();
        acumulador_inseguro = leido + 1;
    }
}

void incrementarSeguro() {
    for (int i = 0; i < INCREMENTOS_POR_HILO; ++i) {
        std::lock_guard<std::mutex> lock(mtx);
        acumulador_seguro++;
    }
}
} // namespace

int main() {
    const long esperado = static_cast<long>(NUM_HILOS) * INCREMENTOS_POR_HILO;

    {
        std::vector<std::thread> hilos;
        hilos.reserve(NUM_HILOS);
        for (int i = 0; i < NUM_HILOS; ++i) hilos.emplace_back(incrementarInseguro);
        for (auto& h : hilos) h.join();
    }
    {
        std::vector<std::thread> hilos;
        hilos.reserve(NUM_HILOS);
        for (int i = 0; i < NUM_HILOS; ++i) hilos.emplace_back(incrementarSeguro);
        for (auto& h : hilos) h.join();
    }

    std::cout << "=== Prueba de condicion de carrera (seccion 3.1) ===\n";
    std::cout << "Valor esperado (N hilos x incrementos):  " << esperado << "\n";
    std::cout << "Acumulador SIN mutex (inseguro):          " << acumulador_inseguro;
    std::cout << (acumulador_inseguro != esperado
                      ? "   <-- datos perdidos (condicion de carrera reproducida)\n"
                      : "   (coincidio en esta corrida, pero no esta garantizado sin mutex)\n");
    std::cout << "Acumulador CON mutex (seguro):             " << acumulador_seguro;
    std::cout << (acumulador_seguro == esperado ? "   <-- OK, sin perdida de datos\n" : "   <-- ERROR INESPERADO\n");

    // El criterio de exito de esta prueba es la version CON mutex: debe ser
    // siempre exacta. La version sin mutex se deja solo con fines
    // demostrativos/comparativos.
    return (acumulador_seguro == esperado) ? 0 : 1;
}
