// Executa somente a construcao de JSON, com interfaces simuladas, sem iniciar tarefas.
#define CONFIG_IDF_TARGET_ESP32S3 1
#include "../firmware/adxl355_wifi_sd/node.cpp"
#include <fstream>
#include <cassert>
SerialMock Serial;ESPMock ESP;WiFiMock WiFi;SDMock SD;
int SerialMock::printf(const char*,...){return 0;}
int main(int argc,char **argv) {
  assert(argc==2);
  identity[0]=0xAD;identity[1]=0x1D;identity[2]=0xED;identity[3]=1;
  Job j=defaults();strcpy(j.request,"json-teste");strcpy(j.note,"linha 1\nlinha \"2\" e \\ final");
  Runtime s{};strcpy(s.run,"SINTETICO_JSON");s.repetition=1;s.reason=Reason::TIME;s.written=15000;s.acquired=15000;s.startUs=200000;s.endUs=30200000;
  String encoded=metadata(j,s,true);
  std::ofstream file(argv[1]);file<<encoded.c_str();assert(file.good());
}
