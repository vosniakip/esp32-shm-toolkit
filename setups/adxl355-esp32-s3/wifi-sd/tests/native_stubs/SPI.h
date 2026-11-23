#pragma once
#include "Arduino.h"
#define FSPI 1
#define HSPI 2
#define MSBFIRST 1
#define SPI_MODE0 0
struct SPISettings{SPISettings(unsigned,int,int){}};
struct SPIClass{SPIClass(int){}void begin(int,int,int,int){}void beginTransaction(SPISettings){}void endTransaction(){}uint8_t transfer(uint8_t){return 0;}};
