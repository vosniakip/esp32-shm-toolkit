#pragma once
#include "Arduino.h"
struct Preferences{bool begin(const char*,bool){return true;}bool getBool(const char*,bool v){return v;}size_t putBool(const char*,bool){return 1;}
uint32_t getUInt(const char*,uint32_t v){return v;}size_t putUInt(const char*,uint32_t){return 4;}size_t putBytes(const char*,const void*,size_t n){return n;}
size_t getBytesLength(const char*){return 0;}size_t getBytes(const char*,void*,size_t){return 0;}};
