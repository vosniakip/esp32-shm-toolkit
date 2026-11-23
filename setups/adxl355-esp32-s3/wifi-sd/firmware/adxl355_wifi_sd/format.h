#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>
// ESP32-S3 e little-endian. O leitor Python usa '<', sem depender do alinhamento do PC.
#pragma pack(push,1)
struct RawHeader {
  char magic[8]; uint16_t version,headerBytes,recordBytes,reserved;
  uint32_t rateHz,rangeG; uint64_t durationUs; char runId[32];
};
struct RawRecord {
  uint64_t index,timeUs; int32_t x,y,z; int16_t temperature; uint16_t flags;
};
struct BlockHeader {
  char magic[4]; uint32_t sequence; uint16_t records,recordBytes; uint32_t crc32;
};
struct RawFooter { char magic[4]; uint32_t blocks; uint64_t records; };
#pragma pack(pop)
static_assert(sizeof(RawHeader)==64,"Header ABI");
static_assert(sizeof(RawRecord)==32,"Record ABI");
static_assert(sizeof(BlockHeader)==16,"Block ABI");
static_assert(sizeof(RawFooter)==16,"Footer ABI");
enum RecordFlag : uint16_t { TEMP_FRESH=1, TEMP_INVALID=2 };
inline uint32_t crc32bytes(const uint8_t *p,size_t n) {
  uint32_t c=0xFFFFFFFFu;
  while(n--) { c^=*p++; for(unsigned j=0;j<8;++j) c=(c>>1)^((0u-(c&1u))&0xEDB88320u); }
  return c^0xFFFFFFFFu;
}
inline int32_t decode20(const uint8_t *b) {
  uint32_t u=(uint32_t(b[0])<<12)|(uint32_t(b[1])<<4)|(uint32_t(b[2])>>4);
  return (u&0x80000u)?int32_t(int64_t(u)-0x100000LL):int32_t(u);
}
inline bool fifoTripleOK(const uint8_t *b) {
  return !(b[2]&2) && !(b[5]&2) && !(b[8]&2) &&
         (b[2]&1) && !(b[5]&1) && !(b[8]&1);
}
inline bool safeId(const char *s,size_t maxLen) {
  if(!s || !*s || strlen(s)>maxLen) return false;
  for(;*s;++s) if(!((*s>='a'&&*s<='z')||(*s>='A'&&*s<='Z')||
                  (*s>='0'&&*s<='9')||*s=='_'||*s=='-')) return false;
  return true;
}
