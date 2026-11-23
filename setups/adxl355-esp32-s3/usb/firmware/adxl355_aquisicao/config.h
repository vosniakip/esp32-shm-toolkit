#pragma once
#include <stdint.h>
// Nomes do modulo: CS/SCL, MOSI/SDA, SCLK, MISO/AS, DRDY.
constexpr int PIN_CS=10, PIN_MOSI=11, PIN_SCK=12, PIN_MISO=13, PIN_DRDY=14;
constexpr uint32_t SERIAL_BAUD=921600, SPI_HZ=1000000;
constexpr uint16_t SAMPLE_RATE_HZ=500; // 250 ou 500
constexpr uint8_t RANGE_G=2; // 2, 4 ou 8
constexpr unsigned QUEUE_LENGTH=512;
constexpr uint32_t MAX_DURATION_MS=86400000;
static_assert(SAMPLE_RATE_HZ==250 || SAMPLE_RATE_HZ==500,"Taxa implementada: 250 ou 500 Hz");
static_assert(RANGE_G==2 || RANGE_G==4 || RANGE_G==8,"Faixa: 2, 4 ou 8 g");
