#include <cassert>
#include <initializer_list>
#include "../firmware/adxl355_aquisicao/codec.h"
int main() {
 for(int32_t v: {int32_t(-524288),int32_t(-256000),int32_t(-1),int32_t(0),int32_t(1),int32_t(256000),int32_t(524287)}) {
   uint32_t raw=uint32_t(v)&0xFFFFF; uint8_t b[3]={uint8_t(raw>>12),uint8_t(raw>>4),uint8_t((raw<<4)|15)}; assert(decode20(b)==v);
 }
 assert(crc16("123456789",9)==0x29B1);
}
