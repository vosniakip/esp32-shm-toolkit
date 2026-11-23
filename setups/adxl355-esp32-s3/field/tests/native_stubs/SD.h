#pragma once
#include "Arduino.h"
#include "SPI.h"
#define FILE_WRITE "w"
#define FILE_READ "r"
struct File{operator bool()const{return true;}size_t write(const uint8_t*,size_t n){return n;}size_t print(const String&s){return s.length();}
void flush(){}int getWriteError(){return 0;}void close(){}bool available(){return false;}size_t read(uint8_t*,size_t){return 0;}String readString(){return {};}
size_t size(){return 0;}bool seek(size_t){return true;}File openNextFile(){return {};}bool isDirectory(){return true;}const char*name(){return "";}};
struct SDMock{bool begin(int,SPIClass&,unsigned){return true;}bool exists(const char*){return false;}bool mkdir(const char*){return true;}
bool remove(const char*){return true;}bool rename(const char*,const char*){return true;}File open(const char*,const char * = "r"){return {};}
uint64_t totalBytes(){return 0;}uint64_t usedBytes(){return 0;}};extern SDMock SD;
