#include <chrono>
#include <iostream>
#include <fstream>
#include <thread>

std::string currTemp;
std::string currHum;

void read_hum() {
    std::ifstream file("humidity.txt");

    if(!file.is_open()) {
        std::cerr << "err: could not open file" << std::endl;
        return;
    }

    std::string line; 

    while(std::getline(file, line)) {
        // std::cout << "\rhumidity: " << line;
        currHum = line;
    }

    file.close();
}

void read_temp() {
    std::ifstream file("temperature.txt");

    if(!file.is_open()) {
        std::cerr << "err: could not open file" << std::endl;
        return;
    }

    std::string line;

    while(std::getline(file, line)) {
        // std::cout << "\n\rtemperature: " << line;
        currTemp = line;
    }

    file.close();
}

int main() {
    std::thread t1(read_temp);
    std::thread t2(read_hum);

    while(1) {
        std::cout << "\rtemp: " << currTemp << "C" << " hum: " << currHum << "%";
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }

    t1.join();
    t2.join();
}
