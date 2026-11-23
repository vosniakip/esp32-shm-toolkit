#pragma once
#include <stdint.h>
#include <stddef.h>
inline int32_t decode20(const uint8_t *b) {
  uint32_t v=(uint32_t(b[0])<<12)|(uint32_t(b[1])<<4)|(b[2]>>4);
  return (v&0x80000) ? int32_t(v)-0x100000 : int32_t(v);
}
inline uint16_t crc16(const char *data,size_t n) {
  uint16_t crc=0xFFFF;
  for(size_t i=0;i<n;++i) {
    crc^=uint16_t(uint8_t(data[i]))<<8;
    for(int j=0;j<8;++j) crc=(crc&0x8000) ? uint16_t((crc<<1)^0x1021) : uint16_t(crc<<1);
  }
  return crc;
}
