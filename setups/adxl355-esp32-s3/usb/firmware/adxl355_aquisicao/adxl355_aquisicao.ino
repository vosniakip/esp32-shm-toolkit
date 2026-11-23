/* ADXL355 + ESP32-S3 — aquisicao de bancada 1.0.0.
 * 3V -> 3V3; GND -> GND; DRDY -> 14; INT1 livre;
 * SCLK -> 12; MISO/AS -> 13; MOSI/SDA -> 11; CS/SCL -> 10.
 * SPI modo 0. Comandos: INFO, START,5000, STOP, HELP + Nova linha.
 */
#include <Arduino.h>
#include <SPI.h>
#include <esp_timer.h>
#include <inttypes.h>
#include <stdlib.h>
#include <string.h>
#include "config.h"
#include "codec.h"
#if !defined(CONFIG_IDF_TARGET_ESP32S3)
#error "Selecione uma placa ESP32-S3 no Arduino IDE."
#endif
constexpr uint8_t REG_STATUS=0x04,REG_TEMP2=0x06,REG_XDATA3=0x08;
constexpr uint8_t REG_FILTER=0x28,REG_INTMAP=0x2A,REG_SYNC=0x2B;
constexpr uint8_t REG_RANGE=0x2C,REG_POWER=0x2D,REG_RESET=0x2F;
constexpr uint8_t FILTER_VALUE=SAMPLE_RATE_HZ==500?0x03:0x04;
constexpr uint8_t RANGE_VALUE=RANGE_G==2?0x01:(RANGE_G==4?0x02:0x03);
constexpr uint32_t SENSITIVITY=512000U/RANGE_G;
const SPISettings sensorSPI(SPI_HZ,MSBFIRST,SPI_MODE0);
portMUX_TYPE irqMux=portMUX_INITIALIZER_UNLOCKED;
volatile uint32_t irqCounter=0;
volatile int64_t irqTimeUs=0;
void ARDUINO_ISR_ATTR onDataReady() {
  const int64_t now=esp_timer_get_time();
  portENTER_CRITICAL_ISR(&irqMux);
  irqCounter=irqCounter+1; irqTimeUs=now;
  portEXIT_CRITICAL_ISR(&irqMux);
}
void snapshot(uint32_t &count,int64_t &timeUs) {
  portENTER_CRITICAL(&irqMux); count=irqCounter; timeUs=irqTimeUs; portEXIT_CRITICAL(&irqMux);
}
void readRegisters(uint8_t reg,uint8_t *out,size_t n) {
  SPI.beginTransaction(sensorSPI); digitalWrite(PIN_CS,LOW);
  SPI.transfer(uint8_t((reg<<1)|1));
  for(size_t i=0;i<n;++i) out[i]=SPI.transfer(0);
  digitalWrite(PIN_CS,HIGH); SPI.endTransaction();
}
uint8_t readRegister(uint8_t reg) { uint8_t value; readRegisters(reg,&value,1); return value; }
void writeRegister(uint8_t reg,uint8_t value) {
  SPI.beginTransaction(sensorSPI); digitalWrite(PIN_CS,LOW);
  SPI.transfer(uint8_t(reg<<1)); SPI.transfer(value);
  digitalWrite(PIN_CS,HIGH); SPI.endTransaction();
}
uint8_t ids[4]={};
bool ready=false;
bool readIdentity() { readRegisters(0,ids,4); return ids[0]==0xAD && ids[1]==0x1D && ids[2]==0xED; }
bool registersOK() {
  return readIdentity() && readRegister(REG_FILTER)==FILTER_VALUE &&
    (readRegister(REG_RANGE)&3)==RANGE_VALUE && (readRegister(REG_POWER)&7)==0 &&
    readRegister(REG_SYNC)==0 && readRegister(REG_INTMAP)==0;
}
bool initializeSensor() {
  if(!readIdentity()) return false;
  writeRegister(REG_RESET,0x52); delay(20);
  uint32_t start=millis();
  while(readRegister(REG_STATUS)&0x10) { if(millis()-start>500) return false; delay(1); }
  writeRegister(REG_POWER,1); // standby
  writeRegister(REG_FILTER,FILTER_VALUE); // HPF desligado
  writeRegister(REG_RANGE,RANGE_VALUE);
  writeRegister(REG_INTMAP,0); // DRDY e um pino dedicado
  writeRegister(REG_SYNC,0); // relogio interno
  writeRegister(REG_POWER,0); // medicao, temperatura e DRDY ativos
  delay(100); return registersOK();
}
int32_t readTemperature() {
  for(int tries=0;tries<3;++tries) {
    uint8_t b[2]; readRegisters(REG_TEMP2,b,2);
    if((readRegister(REG_TEMP2)&15)==(b[0]&15)) return ((b[0]&15)<<8)|b[1];
  }
  return -1;
}
struct Sample { uint64_t index,tUs; int32_t x,y,z,temp; uint32_t lost,droppedQueue,discardedReads,spiErrors; };
Sample queueData[QUEUE_LENGTH];
unsigned head=0,tail=0,queued=0;
uint32_t lost=0,droppedQueue=0,discardedReads=0,spiErrors=0,lastIrq=0;
uint64_t eventIndex=0,acquired=0,sent=0;
int64_t startUs=0,durationUs=0,lastEventUs=0,lastCheckUs=0,drainStartUs=0;
bool running=false,draining=false;
const char *endReason="ocioso";
char tx[192],command[80];
size_t txLength=0,txOffset=0;
unsigned commandLength=0;
bool commandOverflow=false;
void printInfo() {
  Serial.printf("#INFO,formato=ADXL355_S3_V1,sensor_modelo=ADXL355,fw=1.0.0,board=ESP32-S3,pronto=%u,devid_ad=0x%02X,devid_mst=0x%02X,partid=0x%02X,revid=0x%02X,fs_nominal_hz=%u,faixa_g=%u,sensibilidade_lsb_g=%lu,lpf_hz=%.2f,hpf=0,spi_hz=%lu,gpio_cs=%d,gpio_mosi=%d,gpio_sck=%d,gpio_miso=%d,gpio_drdy=%d,checksum=CRC16_CCITT_FALSE,tempo=esp_timer_drdy\n",
    unsigned(ready),ids[0],ids[1],ids[2],ids[3],SAMPLE_RATE_HZ,RANGE_G,
    (unsigned long)SENSITIVITY,SAMPLE_RATE_HZ/4.0,(unsigned long)SPI_HZ,
    PIN_CS,PIN_MOSI,PIN_SCK,PIN_MISO,PIN_DRDY);
}
void finishAcquisition(const char *reason) {
  if(!running) return;
  running=false; draining=true; drainStartUs=esp_timer_get_time(); endReason=reason;
}
void startAcquisition(uint32_t ms) {
  if(running||draining) { Serial.println("#ERRO,aquisicao_em_andamento"); return; }
  ready=registersOK();
  if(!ready) { printInfo(); Serial.println("#FATAL,sensor_nao_pronto"); return; }
  head=tail=queued=0; txLength=txOffset=0;
  lost=droppedQueue=discardedReads=spiErrors=0; eventIndex=acquired=sent=0;
  Serial.printf("#START,duracao_ms=%lu\n",(unsigned long)ms);
  startUs=esp_timer_get_time(); durationUs=int64_t(ms)*1000;
  lastEventUs=lastCheckUs=startUs; int64_t ignored; snapshot(lastIrq,ignored); running=true;
}
void processCommand(const char *cmd) {
  if(!strcmp(cmd,"STOP")) { finishAcquisition("comando_stop"); return; }
  if(!strcmp(cmd,"INFO")) {
    if(running||draining) Serial.println("#ERRO,INFO_somente_em_repouso");
    else { ready=registersOK(); printInfo(); } return;
  }
  if(!strcmp(cmd,"HELP")) { Serial.println("#HELP,INFO;START,milissegundos;STOP"); return; }
  if(!strncmp(cmd,"START,",6)) {
    char *end; unsigned long value=strtoul(cmd+6,&end,10);
    if(cmd[6]=='-' || end==cmd+6 || *end || value<100 || value>MAX_DURATION_MS)
      Serial.println("#ERRO,duracao_invalida_100_a_86400000_ms");
    else startAcquisition(uint32_t(value)); return;
  }
  Serial.println("#ERRO,comando_desconhecido_use_HELP");
}
void receiveCommands() {
  for(unsigned i=0;i<48 && Serial.available();++i) {
    char c=Serial.read(); if(c=='\r') continue;
    if(c=='\n') {
      if(commandOverflow) Serial.println("#ERRO,comando_muito_longo");
      else if(commandLength) { command[commandLength]=0; processCommand(command); }
      commandLength=0; commandOverflow=false;
    } else if(commandLength<sizeof(command)-1) command[commandLength++]=c;
    else commandOverflow=true;
  }
}
void acquireIfReady() {
  int64_t now=esp_timer_get_time();
  if(now-startUs>=durationUs) { finishAcquisition("tempo_concluido"); return; }
  if(now-lastEventUs>1500000) { finishAcquisition("sem_drdy"); return; }
  uint32_t count; int64_t stamp; snapshot(count,stamp);
  uint32_t delta=count-lastIrq; if(!delta) return;
  lastIrq=count; lastEventUs=stamp; eventIndex+=delta; lost+=delta-1;
  int64_t period=1000000/SAMPLE_RATE_HZ;
  if(stamp<startUs || now-stamp>period*3/4) { ++discardedReads; ++lost; return; }
  uint8_t b[9]; readRegisters(REG_XDATA3,b,sizeof(b));
  uint32_t after; int64_t afterStamp; snapshot(after,afterStamp);
  if(after!=count || esp_timer_get_time()-stamp>=period) { ++discardedReads; ++lost; return; }
  int32_t temp=readTemperature();
  if(now-lastCheckUs>=1000000) {
    lastCheckUs=now;
    if(!registersOK()) { ready=false; ++spiErrors; ++lost; finishAcquisition("falha_identificacao_ou_configuracao"); return; }
  }
  ++acquired;
  if(queued==QUEUE_LENGTH) { ++droppedQueue; ++lost; return; }
  queueData[head]={eventIndex-1,uint64_t(stamp-startUs),decode20(b),decode20(b+3),decode20(b+6),temp,lost,droppedQueue,discardedReads,spiErrors};
  head=(head+1)%QUEUE_LENGTH; ++queued;
}
void transmitOneChunk() {
  if(!queued) return;
  if(!txLength) {
    const Sample &s=queueData[tail];
    int n=snprintf(tx,sizeof(tx),"D,%" PRIu64 ",%" PRIu64 ",%ld,%ld,%ld,%ld,%lu,%lu,%lu,%lu",s.index,s.tUs,(long)s.x,(long)s.y,(long)s.z,(long)s.temp,(unsigned long)s.lost,(unsigned long)s.droppedQueue,(unsigned long)s.discardedReads,(unsigned long)s.spiErrors);
    uint16_t checksum=crc16(tx,size_t(n));
    n+=snprintf(tx+n,sizeof(tx)-n,",%04X\n",checksum); txLength=size_t(n); txOffset=0;
  }
  int available=Serial.availableForWrite(); if(available<=0) return;
  size_t remaining=txLength-txOffset,chunk=remaining<size_t(available)?remaining:size_t(available);
  txOffset+=Serial.write((const uint8_t*)tx+txOffset,chunk);
  if(txOffset==txLength) { txLength=txOffset=0; tail=(tail+1)%QUEUE_LENGTH; --queued; ++sent; }
}
void setup() {
#if !ARDUINO_USB_CDC_ON_BOOT
  Serial.setTxBufferSize(2048);
#endif
  Serial.begin(SERIAL_BAUD); delay(1200);
  pinMode(PIN_CS,OUTPUT); digitalWrite(PIN_CS,HIGH); pinMode(PIN_DRDY,INPUT);
  SPI.begin(PIN_SCK,PIN_MISO,PIN_MOSI,PIN_CS);
  ready=initializeSensor(); attachInterrupt(digitalPinToInterrupt(PIN_DRDY),onDataReady,RISING);
  Serial.println("#READY"); printInfo();
  if(!ready) Serial.println("#FATAL,identificacao_ou_configuracao_invalida");
}
void loop() {
  if(running) acquireIfReady();
  if(!txLength) receiveCommands(); // nao intercala texto no meio de um pacote D
  transmitOneChunk();
  if(draining) {
    if(queued && esp_timer_get_time()-drainStartUs>5000000) {
      lost+=queued; droppedQueue+=queued; queued=0; txLength=txOffset=0;
      endReason="timeout_transmissao"; Serial.println();
    }
    if(!queued) {
      Serial.printf("#END,motivo=%s,amostras_lidas=%" PRIu64 ",enviadas=%" PRIu64 ",perdidas=%lu,descartes_fila=%lu,leituras_descartadas=%lu,erros_spi=%lu,eventos_drdy=%" PRIu64 "\n",endReason,acquired,sent,(unsigned long)lost,(unsigned long)droppedQueue,(unsigned long)discardedReads,(unsigned long)spiErrors,eventIndex);
      draining=false;
    }
  }
  delay(0);
}
