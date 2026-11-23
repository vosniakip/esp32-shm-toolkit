#include "../firmware/adxl355_wifi_sd/format.h"
#include <cassert>
#include <fstream>
#include <cstring>
int main(int argc,char **argv) {
  assert(argc==2);
  const char *check="123456789";
  assert(crc32bytes(reinterpret_cast<const uint8_t*>(check),9)==0xCBF43926u);
  uint8_t b[9]={0x80,0,1,0x7F,0xFF,0xF0,0xFF,0xFF,0xF0};
  assert(fifoTripleOK(b));assert(decode20(b)==-524288);assert(decode20(b+3)==524287);assert(decode20(b+6)==-1);
  b[5]|=2;assert(!fifoTripleOK(b));
  assert(safeId("abc_1-2",7));assert(!safeId("../x",10));assert(!safeId("",10));
  RawHeader h{};memcpy(h.magic,"A355SD3",8);h.version=3;h.headerBytes=64;h.recordBytes=32;h.rateHz=500;h.rangeG=2;h.durationUs=1000000;strcpy(h.runId,"SINTETICO_CPP");
  RawRecord records[2]={{0,500,-524288,524287,-1,1885,TEMP_FRESH},{1,2500,0,0,256000,1885,0}};
  BlockHeader block{};memcpy(block.magic,"BLK3",4);block.records=2;block.recordBytes=32;
  block.crc32=crc32bytes(reinterpret_cast<const uint8_t*>(records),sizeof(records));
  RawFooter footer{};memcpy(footer.magic,"END3",4);footer.blocks=1;footer.records=2;
  std::ofstream file(argv[1],std::ios::binary);
  file.write(reinterpret_cast<const char*>(&h),sizeof(h));file.write(reinterpret_cast<const char*>(&block),sizeof(block));
  file.write(reinterpret_cast<const char*>(records),sizeof(records));file.write(reinterpret_cast<const char*>(&footer),sizeof(footer));
  assert(file.good());
}
