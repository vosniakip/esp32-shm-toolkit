/* ADXL355 + ESP32-S3, Wi-Fi de bancada e microSD. Versao 3.0.0.
 * Leitura pelo FIFO com timestamps reais de DRDY, sem interpolar lacunas.
 * As bibliotecas usadas pertencem ao core Arduino-ESP32 3.x.
 * Leia docs/GUIA_COMPLETO.md antes de energizar. Sem espera por um host USB.
 */
#include <Arduino.h>
#include <SPI.h>
#include <WiFi.h>
#include <WebServer.h>
#include <SD.h>
#include <Preferences.h>
#include <esp_timer.h>
#include <esp_system.h>
#include <mbedtls/sha256.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <freertos/queue.h>
#include <inttypes.h>
#include <stdlib.h>
#include <atomic>
#include "config.h"
#include "format.h"
#include "web_ui.h"
#if !defined(CONFIG_IDF_TARGET_ESP32S3)
#error "Selecione ESP32S3 Dev Module (ESP32-S3). Este firmware nao e para ESP32 DevKit V1."
#endif

SPIClass sensorBus(FSPI),cardBus(HSPI);
WebServer server(80);
Preferences preferences;
TaskHandle_t acquisitionHandle=nullptr,storageHandle=nullptr;
QueueHandle_t recordQueue=nullptr,jobQueue=nullptr;

enum class Phase:uint8_t { IDLE,PREPARING,ARMED,ACQUIRING,DRAINING,FINALIZING,INTERVAL,READY,INTERRUPTED,ERROR };
enum class Reason:uint8_t { NONE,TIME,STOP,NO_DRDY,FIFO_OVERFLOW,FIFO_INVALID,IRQ_OVERFLOW,
  DRDY_GAP,BUFFER_OVERFLOW,SPI_ERROR,SD_ERROR,CANCELLED };
const char *phaseName(Phase s) {
  switch(s) {
    case Phase::IDLE:return "ocioso";case Phase::PREPARING:return "preparando";
    case Phase::ARMED:return "aguardando_inicio";case Phase::ACQUIRING:return "adquirindo";
    case Phase::DRAINING:return "esvaziando_buffer";case Phase::FINALIZING:return "finalizando";
    case Phase::INTERVAL:return "intervalo";case Phase::READY:return "concluido";
    case Phase::INTERRUPTED:return "interrompido";
    default:return "falha";
  }
}
const char *reasonName(Reason s) {
  switch(s) {
    case Reason::TIME:return "tempo_concluido";case Reason::STOP:return "comando_stop";
    case Reason::NO_DRDY:return "sem_drdy";case Reason::FIFO_OVERFLOW:return "fifo_overrun";
    case Reason::FIFO_INVALID:return "fifo_invalido";case Reason::IRQ_OVERFLOW:return "fila_drdy_cheia";
    case Reason::DRDY_GAP:return "lacuna_drdy";case Reason::BUFFER_OVERFLOW:return "buffer_cheio";
    case Reason::SPI_ERROR:return "falha_identificacao_ou_configuracao";
    case Reason::SD_ERROR:return "falha_microSD";case Reason::CANCELLED:return "cancelado_antes_do_inicio";
    default:return "nenhum";
  }
}
struct Job {
  char sensor[25],mount[33],experiment[25],position[25],reference[12],note[241],calibration[41],request[65];
  uint32_t durationS,rateHz,rangeG,delayS,intervalS;uint16_t repetition,repetitions;bool quiet;
};
struct Runtime {
  Phase phase;Reason reason;bool busy,rawFinalized;char run[32];
  uint32_t written,acquired,queuePeak,lostLowerBound,spiErrors,fifoOverruns,irqOverruns,queueDrops;
  uint16_t repetition,seriesDone,seriesTotal;
  int64_t startUs,lastSampleUs,endUs;
};
Runtime runtime{};
Job currentJob{};
portMUX_TYPE stateMux=portMUX_INITIALIZER_UNLOCKED;
Runtime snapshot() { portENTER_CRITICAL(&stateMux);Runtime s=runtime;portEXIT_CRITICAL(&stateMux);return s; }
void phase(Phase s) { portENTER_CRITICAL(&stateMux);runtime.phase=s;portEXIT_CRITICAL(&stateMux); }
void reason(Reason r) { portENTER_CRITICAL(&stateMux);if(runtime.reason==Reason::NONE)runtime.reason=r;portEXIT_CRITICAL(&stateMux); }
std::atomic<bool> stopRequested{false},acquisitionFinished{true},radioOffRequested{false},radioIsOff{false},restoreRadioRequested{false};
std::atomic<bool> sensorReady{false},cardReady{false},tasksReady{false};
bool apStarted=false;
uint8_t identity[4]={};
uint32_t bootCount=0,bootRandom=0,runCounter=0;
uint64_t cardCapacity=0,cardFree=0;
int64_t clockEpochMs=0,clockBootUs=0;
bool clockKnown=false;
String lastRequest,lastSeriesIds;

String quote(const String &s) {
  String out="\"";out.reserve(s.length()+12);
  for(size_t i=0;i<s.length();++i) {
    unsigned char c=s[i];
    if(c=='"'||c=='\\'){out+='\\';out+=char(c);}else if(c=='\n')out+="\\n";
    else if(c=='\r')out+="\\r";else if(c=='\t')out+="\\t";
    else if(c<32){char b[7];snprintf(b,sizeof(b),"\\u%04x",c);out+=b;}else out+=char(c);
  }
  return out+'"';
}
String u64(uint64_t v) { char b[24];snprintf(b,sizeof(b),"%" PRIu64,v);return String(b); }
String i64(int64_t v) { char b[24];snprintf(b,sizeof(b),"%" PRId64,v);return String(b); }
String configuration(const Job &j) {
  return "{\"faixa_g\":"+String(j.rangeG)+",\"fs_nominal_hz\":"+String(j.rateHz)+
    ",\"sensibilidade_lsb_g\":"+String(512000UL/j.rangeG)+",\"lpf_hz\":"+String(j.rateHz/4.0,2)+
    ",\"hpf\":0,\"spi_hz\":"+String(SENSOR_SPI_HZ)+",\"sd_spi_hz\":"+String(CARD_SPI_HZ)+
    ",\"gpio_sensor_cs\":"+String(SENSOR_CS)+",\"gpio_sensor_sck\":"+String(SENSOR_SCK)+
    ",\"gpio_sensor_mosi\":"+String(SENSOR_MOSI)+",\"gpio_sensor_miso\":"+String(SENSOR_MISO)+
    ",\"gpio_drdy\":"+String(SENSOR_DRDY)+",\"gpio_sd_cs\":"+String(CARD_CS)+
    ",\"gpio_sd_sck\":"+String(CARD_SCK)+",\"gpio_sd_mosi\":"+String(CARD_MOSI)+",\"gpio_sd_miso\":"+String(CARD_MISO)+
    ",\"tempo\":\"DRDY_ISR_esp_timer_64bit\",\"leitura\":\"FIFO_com_pareamento_DRDY\"}";
}
String metadata(const Job &j,const Runtime &s,bool finalized) {
  String out;out.reserve(3200);
  out="{\"schema\":\"ADXL355_SD_META_V3\",\"firmware\":"+quote(FW_VERSION)+
    ",\"run_id\":"+quote(s.run)+",\"request_id\":"+quote(j.request)+
    ",\"sensor_modelo\":\"ADXL355\",\"devid_ad\":"+String(identity[0])+",\"devid_mst\":"+String(identity[1])+
    ",\"partid\":"+String(identity[2])+",\"revid\":"+String(identity[3])+
    ",\"sensor\":"+quote(j.sensor)+",\"montagem\":"+quote(j.mount)+
    ",\"ensaio\":"+quote(j.experiment)+",\"posicao\":"+quote(j.position)+
    ",\"referencial_posicao\":"+quote(j.reference)+",\"repeticao\":"+String(s.repetition)+
    ",\"nota\":"+quote(j.note)+",\"calibracao_id\":"+quote(j.calibration)+
    ",\"configuracao\":"+configuration(j)+",\"duracao_solicitada_s\":"+String(j.durationS)+
    ",\"radio\":"+quote(j.quiet?"desligado":"ativo")+",\"boot_count\":"+String(bootCount)+
    ",\"start_boot_us\":"+i64(s.startUs)+",\"end_boot_us\":"+i64(s.endUs)+
    ",\"preroll_us\":"+String(SETTLING_US)+",\"epoch_inicio_ms\":";
  out+=(clockKnown&&s.startUs>0)?i64(clockEpochMs+(s.startUs-clockBootUs)/1000):"null";
  out+=",\"origem_hora\":"+quote(clockKnown?"computador_sem_garantia_de_sincronismo":"indisponivel")+
    ",\"sincronismo_entre_nos_validado\":false,\"arquivo_finalizado\":"+String(finalized?"true":"false")+
    ",\"captura_completa\":"+String(finalized&&s.reason==Reason::TIME?"true":"false")+
    ",\"motivo\":"+quote(reasonName(s.reason))+",\"amostras_gravadas\":"+String(s.written)+
    ",\"amostras_adquiridas\":"+String(s.acquired)+",\"buffer_pico_registros\":"+String(s.queuePeak)+
    ",\"buffer_capacidade_registros\":"+String(SAMPLE_QUEUE_LENGTH)+
    ",\"perdas_limite_inferior\":"+String(s.lostLowerBound)+",\"erros_spi\":"+String(s.spiErrors)+
    ",\"fifo_overruns\":"+String(s.fifoOverruns)+",\"fila_drdy_overruns\":"+String(s.irqOverruns)+
    ",\"descartes_fila\":"+String(s.queueDrops)+
    ",\"temperatura\":\"12_bits_brutos; leitura_1_Hz_mantida_entre_atualizacoes\"}";
  return out;
}

// Somente acquisitionTask acessa este barramento depois de setup().
void readRegisters(uint8_t reg,uint8_t *b,size_t n) {
  sensorBus.beginTransaction(SPISettings(SENSOR_SPI_HZ,MSBFIRST,SPI_MODE0));
  digitalWrite(SENSOR_CS,LOW);sensorBus.transfer(uint8_t((reg<<1)|1));
  for(size_t k=0;k<n;++k)b[k]=sensorBus.transfer(0);
  digitalWrite(SENSOR_CS,HIGH);sensorBus.endTransaction();
}
uint8_t readRegister(uint8_t reg){uint8_t b;readRegisters(reg,&b,1);return b;}
void writeRegister(uint8_t reg,uint8_t v) {
  sensorBus.beginTransaction(SPISettings(SENSOR_SPI_HZ,MSBFIRST,SPI_MODE0));
  digitalWrite(SENSOR_CS,LOW);sensorBus.transfer(uint8_t(reg<<1));sensorBus.transfer(v);
  digitalWrite(SENSOR_CS,HIGH);sensorBus.endTransaction();
}
bool identityOK(){readRegisters(0,identity,4);return identity[0]==0xAD&&identity[1]==0x1D&&identity[2]==0xED;}
bool registersOK(const Job &j) {
  return identityOK()&&readRegister(0x28)==(j.rateHz==500?3:4)&&
    (readRegister(0x2C)&3)==(j.rangeG==2?1:(j.rangeG==4?2:3))&&
    (readRegister(0x2D)&7)==0&&readRegister(0x2B)==0&&readRegister(0x2A)==0;
}
bool initializeSensor() {
  if(!identityOK())return false;
  writeRegister(0x2F,0x52);delay(20);
  for(unsigned k=0;readRegister(4)&0x10;++k){if(k>=500)return false;delay(1);}
  writeRegister(0x2D,1);writeRegister(0x28,3);writeRegister(0x2C,1);writeRegister(0x2B,0);writeRegister(0x2A,0);
  writeRegister(0x2D,0);delay(10);Job j{};j.rateHz=500;j.rangeG=2;return registersOK(j);
}
int16_t temperature() {
  for(unsigned k=0;k<3;++k){uint8_t b[2];readRegisters(6,b,2);if((readRegister(6)&15)==(b[0]&15))return int16_t(((b[0]&15)<<8)|b[1]);}
  return -1;
}
struct IrqEvent {uint64_t sequence;int64_t stamp;};
IrqEvent irqRing[IRQ_QUEUE_LENGTH];
volatile unsigned irqHead=0,irqTail=0,irqCount=0;
volatile uint64_t irqSequence=0;
volatile bool collectIrq=false,irqOverflow=false;
portMUX_TYPE irqMux=portMUX_INITIALIZER_UNLOCKED;
void ARDUINO_ISR_ATTR dataReady() {
  if(!collectIrq)return;
  int64_t stamp=esp_timer_get_time();BaseType_t wake=pdFALSE;
  portENTER_CRITICAL_ISR(&irqMux);
  uint64_t sequence=irqSequence++;
  if(irqCount<IRQ_QUEUE_LENGTH){irqRing[irqHead]={sequence,stamp};irqHead=(irqHead+1)%IRQ_QUEUE_LENGTH;++irqCount;}
  else irqOverflow=true;
  portEXIT_CRITICAL_ISR(&irqMux);
  if(acquisitionHandle)vTaskNotifyGiveFromISR(acquisitionHandle,&wake);
  if(wake)portYIELD_FROM_ISR();
}
bool popIrq(IrqEvent &e){bool ok=false;portENTER_CRITICAL(&irqMux);if(irqCount){e=irqRing[irqTail];irqTail=(irqTail+1)%IRQ_QUEUE_LENGTH;--irqCount;ok=true;}portEXIT_CRITICAL(&irqMux);return ok;}
void resetIrq(){portENTER_CRITICAL(&irqMux);collectIrq=false;irqHead=irqTail=irqCount=0;irqSequence=0;irqOverflow=false;portEXIT_CRITICAL(&irqMux);}
void stopIrq(){portENTER_CRITICAL(&irqMux);collectIrq=false;portEXIT_CRITICAL(&irqMux);}

void acquisitionTask(void *) {
  for(;;) {
    ulTaskNotifyTake(pdTRUE,portMAX_DELAY);
    if(acquisitionFinished)continue; // Descarta notificacoes DRDY que restaram da campanha anterior.
    Job j=currentJob;
    phase(Phase::ARMED);
    if(j.quiet){
      // Deixa a resposta HTTP de START sair antes de desativar o ponto de acesso.
      int64_t grace=esp_timer_get_time()+1000000;
      while(!radioIsOff&&esp_timer_get_time()<grace&&!stopRequested)vTaskDelay(pdMS_TO_TICKS(5));
      if(!stopRequested){radioOffRequested=true;while(!radioIsOff&&!stopRequested)vTaskDelay(pdMS_TO_TICKS(5));}
    }
    int64_t armedAt=esp_timer_get_time(),deadline=armedAt+int64_t(j.delayS)*1000000;
    while(esp_timer_get_time()<deadline&&!stopRequested)vTaskDelay(pdMS_TO_TICKS(5));
    if(stopRequested){reason(Reason::CANCELLED);acquisitionFinished=true;continue;}
    resetIrq();
    if(!identityOK()){sensorReady=false;reason(Reason::SPI_ERROR);portENTER_CRITICAL(&stateMux);++runtime.spiErrors;portEXIT_CRITICAL(&stateMux);acquisitionFinished=true;continue;}
    writeRegister(0x2D,1);delay(2);
    writeRegister(0x28,j.rateHz==500?3:4);writeRegister(0x2C,j.rangeG==2?1:(j.rangeG==4?2:3));
    writeRegister(0x2A,0);writeRegister(0x2B,0);
    // Em standby, esvazia inclusive dados de campanhas anteriores.
    uint8_t garbage[3];unsigned entries=readRegister(5)&0x7F;
    if(entries>96){reason(Reason::SPI_ERROR);acquisitionFinished=true;continue;}
    for(unsigned k=0;k<entries;++k)readRegisters(0x11,garbage,3);
    readRegister(4);resetIrq();
    int64_t start=esp_timer_get_time()+SETTLING_US;
    portENTER_CRITICAL(&stateMux);runtime.startUs=start;portEXIT_CRITICAL(&stateMux);
    portENTER_CRITICAL(&irqMux);collectIrq=true;portEXIT_CRITICAL(&irqMux);
    writeRegister(0x2D,0);
    int64_t lastEvent=esp_timer_get_time(),lastAccepted=0,lastCheck=lastEvent,lastTemp=0;
    uint64_t firstSequence=0;bool gotFirst=false;int16_t temp=-1;
    while(!stopRequested) {
      int64_t now=esp_timer_get_time();
      if(now-lastEvent>1000000){reason(Reason::NO_DRDY);break;}
      if(irqOverflow){reason(Reason::IRQ_OVERFLOW);portENTER_CRITICAL(&stateMux);++runtime.irqOverruns;++runtime.lostLowerBound;portEXIT_CRITICAL(&stateMux);break;}
      IrqEvent event;
      if(!popIrq(event)){ulTaskNotifyTake(pdTRUE,pdMS_TO_TICKS(10));continue;}
      lastEvent=event.stamp;
      // Esvazia eventos anteriores ao fim, mesmo que a tarefa acorde depois do prazo.
      if(event.stamp>=start+int64_t(j.durationS)*1000000){reason(Reason::TIME);break;}
      uint8_t status=readRegister(4),b[9];
      if(status&4){reason(Reason::FIFO_OVERFLOW);portENTER_CRITICAL(&stateMux);++runtime.fifoOverruns;++runtime.lostLowerBound;portEXIT_CRITICAL(&stateMux);break;}
      unsigned available=readRegister(5)&0x7F;
      if(available<3||available>96){reason(Reason::FIFO_INVALID);portENTER_CRITICAL(&stateMux);++runtime.lostLowerBound;portEXIT_CRITICAL(&stateMux);break;}
      readRegisters(0x11,b,9);
      if(!fifoTripleOK(b)){reason(Reason::FIFO_INVALID);portENTER_CRITICAL(&stateMux);++runtime.lostLowerBound;portEXIT_CRITICAL(&stateMux);break;}
      if(event.stamp<start)continue; // Pre-roll explicitamente excluido.
      if(event.stamp>=start+int64_t(j.durationS)*1000000){reason(Reason::TIME);break;}
      if(lastAccepted && (event.stamp<=lastAccepted||event.stamp-lastAccepted>int64_t(1500000/j.rateHz))){reason(Reason::DRDY_GAP);portENTER_CRITICAL(&stateMux);++runtime.lostLowerBound;portEXIT_CRITICAL(&stateMux);break;}
      if(!gotFirst){firstSequence=event.sequence;gotFirst=true;phase(Phase::ACQUIRING);}
      lastAccepted=event.stamp;
      uint16_t flags=0;
      if(!lastTemp||event.stamp-lastTemp>=1000000){temp=temperature();lastTemp=event.stamp;flags|=TEMP_FRESH;}
      if(temp<0)flags|=TEMP_INVALID;
      if(event.stamp-lastCheck>=1000000){lastCheck=event.stamp;if(!registersOK(j)){sensorReady=false;reason(Reason::SPI_ERROR);portENTER_CRITICAL(&stateMux);++runtime.spiErrors;++runtime.lostLowerBound;portEXIT_CRITICAL(&stateMux);break;}}
      RawRecord rec{event.sequence-firstSequence,uint64_t(event.stamp-start),decode20(b),decode20(b+3),decode20(b+6),temp,flags};
      if(xQueueSend(recordQueue,&rec,0)!=pdTRUE){reason(Reason::BUFFER_OVERFLOW);portENTER_CRITICAL(&stateMux);++runtime.queueDrops;++runtime.lostLowerBound;portEXIT_CRITICAL(&stateMux);break;}
      unsigned queued=uxQueueMessagesWaiting(recordQueue);
      portENTER_CRITICAL(&stateMux);++runtime.acquired;runtime.lastSampleUs=event.stamp;if(queued>runtime.queuePeak)runtime.queuePeak=queued;portEXIT_CRITICAL(&stateMux);
    }
    stopIrq();
    if(stopRequested)reason(snapshot().acquired?Reason::STOP:Reason::CANCELLED);
    portENTER_CRITICAL(&stateMux);runtime.endUs=esp_timer_get_time();portEXIT_CRITICAL(&stateMux);
    phase(Phase::DRAINING);acquisitionFinished=true;
  }
}

String directoryFor(const char *id){return String("/ensaios/")+id;}
bool writeText(const String &path,const String &text) {
  String tmp=path+".tmp";SD.remove(tmp.c_str());File f=SD.open(tmp.c_str(),FILE_WRITE);
  if(!f)return false;size_t n=f.print(text);f.flush();bool ok=n==text.length()&&!f.getWriteError();f.close();
  if(!ok)return false;if(SD.exists(path.c_str())&&!SD.remove(path.c_str()))return false;
  return SD.rename(tmp.c_str(),path.c_str());
}
String hashFile(const String &path) {
  File f=SD.open(path.c_str(),FILE_READ);if(!f)return "";
  mbedtls_sha256_context context;mbedtls_sha256_init(&context);
  if(mbedtls_sha256_starts(&context,0)!=0){f.close();mbedtls_sha256_free(&context);return "";}
  uint8_t b[4096],digest[32];bool ok=true;
  while(f.available()){size_t n=f.read(b,sizeof(b));if(!n||mbedtls_sha256_update(&context,b,n)!=0){ok=false;break;}vTaskDelay(1);}
  if(mbedtls_sha256_finish(&context,digest)!=0)ok=false;
  f.close();mbedtls_sha256_free(&context);if(!ok)return "";
  char hex[65];for(unsigned k=0;k<32;++k)snprintf(hex+2*k,3,"%02x",digest[k]);hex[64]=0;return String(hex);
}
bool appendBlock(File &file,const RawRecord *records,unsigned count,uint32_t sequence) {
  BlockHeader block{};memcpy(block.magic,"BLK3",4);block.sequence=sequence;block.records=count;block.recordBytes=sizeof(RawRecord);
  block.crc32=crc32bytes(reinterpret_cast<const uint8_t*>(records),count*sizeof(RawRecord));
  return file.write(reinterpret_cast<const uint8_t*>(&block),sizeof(block))==sizeof(block)&&
    file.write(reinterpret_cast<const uint8_t*>(records),count*sizeof(RawRecord))==count*sizeof(RawRecord)&&!file.getWriteError();
}
void newRun(const Job &j,unsigned rep,unsigned done) {
  Runtime s{};s.phase=Phase::PREPARING;s.reason=Reason::NONE;s.busy=true;s.repetition=rep;s.seriesDone=done;s.seriesTotal=j.repetitions;
  snprintf(s.run,sizeof(s.run),"%08lX_%08lX_%04lu",(unsigned long)bootCount,(unsigned long)bootRandom,(unsigned long)++runCounter);
  portENTER_CRITICAL(&stateMux);runtime=s;portEXIT_CRITICAL(&stateMux);
}
void storageTask(void *) {
  Job job;
  for(;;) {
    if(xQueueReceive(jobQueue,&job,portMAX_DELAY)!=pdTRUE)continue;
    lastSeriesIds="[";bool allGood=true;
    for(unsigned rep=0;rep<job.repetitions;++rep) {
      currentJob=job;currentJob.repetition=job.repetition+rep;
      newRun(job,currentJob.repetition,rep);Runtime s=snapshot();
      if(rep)lastSeriesIds+=',';lastSeriesIds+=quote(s.run);
      String dir=directoryFor(s.run),part=dir+"/raw.bin.part",raw=dir+"/raw.bin";
      cardCapacity=SD.totalBytes();uint64_t used=SD.usedBytes();cardFree=cardCapacity>used?cardCapacity-used:0;
      uint64_t needed=uint64_t(job.durationS)*job.rateHz*(sizeof(RawRecord)+1)+262144;
      if(!cardReady||cardFree<needed||SD.exists(dir.c_str())||!SD.mkdir(dir.c_str())){reason(Reason::SD_ERROR);allGood=false;break;}
      if(!writeText(dir+"/meta.json",metadata(currentJob,s,false))){reason(Reason::SD_ERROR);allGood=false;break;}
      File file=SD.open(part.c_str(),FILE_WRITE);
      RawHeader header{};memcpy(header.magic,"A355SD3",8);header.version=3;header.headerBytes=64;header.recordBytes=32;
      header.rateHz=job.rateHz;header.rangeG=job.rangeG;header.durationUs=uint64_t(job.durationS)*1000000;strncpy(header.runId,s.run,31);
      if(!file||file.write(reinterpret_cast<const uint8_t*>(&header),sizeof(header))!=sizeof(header)){if(file)file.close();reason(Reason::SD_ERROR);allGood=false;break;}
      xQueueReset(recordQueue);acquisitionFinished=false;xTaskNotifyGive(acquisitionHandle);
      RawRecord block[BLOCK_RECORDS];unsigned count=0;uint32_t blockNumber=0;
      int64_t blockAt=esp_timer_get_time(),flushAt=blockAt;bool diskOK=true;
      while(!acquisitionFinished||uxQueueMessagesWaiting(recordQueue)>0) {
        RawRecord rec;
        if(xQueueReceive(recordQueue,&rec,pdMS_TO_TICKS(10))==pdTRUE)block[count++]=rec;
        int64_t now=esp_timer_get_time();
        if(count&&(count==BLOCK_RECORDS||now-blockAt>=250000||acquisitionFinished)) {
          if(diskOK && appendBlock(file,block,count,blockNumber)){
            ++blockNumber;portENTER_CRITICAL(&stateMux);runtime.written+=count;portEXIT_CRITICAL(&stateMux);
          }else{diskOK=false;reason(Reason::SD_ERROR);stopRequested=true;}
          count=0;blockAt=now;
        }
        if(now-flushAt>=5000000){if(diskOK){file.flush();if(file.getWriteError()){diskOK=false;reason(Reason::SD_ERROR);stopRequested=true;}}flushAt=now;}
      }
      // Uma corrida entre a ultima recepcao e acquisitionFinished pode deixar um bloco local.
      if(count&&diskOK){if(appendBlock(file,block,count,blockNumber)){++blockNumber;portENTER_CRITICAL(&stateMux);runtime.written+=count;portEXIT_CRITICAL(&stateMux);}else diskOK=false;}
      phase(Phase::FINALIZING);s=snapshot();
      RawFooter footer{};memcpy(footer.magic,"END3",4);footer.blocks=blockNumber;footer.records=s.written;
      if(diskOK)diskOK=file.write(reinterpret_cast<const uint8_t*>(&footer),sizeof(footer))==sizeof(footer);
      file.flush();diskOK=diskOK&&!file.getWriteError();file.close();
      bool finalized=diskOK&&SD.rename(part.c_str(),raw.c_str());
      if(!finalized){reason(Reason::SD_ERROR);allGood=false;}
      portENTER_CRITICAL(&stateMux);runtime.rawFinalized=finalized;runtime.seriesDone=rep+1;portEXIT_CRITICAL(&stateMux);
      s=snapshot();
      String log="boot_us,event,value\n"+i64(s.startUs)+",inicio,"+String(s.repetition)+"\n"+
        i64(s.endUs)+",fim,"+reasonName(s.reason)+"\n"+i64(s.endUs)+",amostras_gravadas,"+String(s.written)+"\n";
      bool metaOK=writeText(dir+"/meta.json",metadata(currentJob,s,finalized));
      bool logOK=writeText(dir+"/events.log",log);
      if(finalized&&metaOK&&logOK) {
        String h=hashFile(raw),mh=hashFile(dir+"/meta.json"),lh=hashFile(dir+"/events.log");
        File rawFile=SD.open(raw.c_str(),FILE_READ);uint64_t length=rawFile?rawFile.size():0;rawFile.close();
        String manifest="{\"schema\":\"ADXL355_SD_MANIFEST_V3\",\"run_id\":"+quote(s.run)+
          ",\"raw_bytes\":"+u64(length)+",\"raw_sha256\":"+quote(h)+",\"meta_sha256\":"+quote(mh)+
          ",\"log_sha256\":"+quote(lh)+",\"records\":"+String(s.written)+",\"blocks\":"+String(blockNumber)+"}";
        if(h.length()!=64||mh.length()!=64||lh.length()!=64||!writeText(dir+"/manifest.json",manifest))allGood=false;
      }else allGood=false;
      if(s.reason!=Reason::TIME||!allGood){allGood=false;break;}
      if(rep+1<job.repetitions){
        phase(Phase::INTERVAL);int64_t next=esp_timer_get_time()+int64_t(job.intervalS)*1000000;
        while(esp_timer_get_time()<next&&!stopRequested)vTaskDelay(pdMS_TO_TICKS(20));
        if(stopRequested){allGood=false;break;}
      }
    }
    lastSeriesIds+=']';
    Reason ended=snapshot().reason;
    bool manual=stopRequested&&(ended==Reason::STOP||ended==Reason::CANCELLED||ended==Reason::TIME);
    portENTER_CRITICAL(&stateMux);runtime.busy=false;runtime.phase=allGood?Phase::READY:(manual?Phase::INTERRUPTED:Phase::ERROR);portEXIT_CRITICAL(&stateMux);
    if(job.quiet)restoreRadioRequested=true;
    Serial.printf("#END,estado=%s,run=%s,motivo=%s,gravadas=%lu\n",phaseName(snapshot().phase),snapshot().run,reasonName(snapshot().reason),(unsigned long)snapshot().written);
  }
}

Job defaults() {
  Job j{};strcpy(j.sensor,DEFAULT_NODE);strcpy(j.mount,DEFAULT_MOUNT);strcpy(j.experiment,"funcional");
  strcpy(j.position,"zpos");strcpy(j.reference,"conjunto");strcpy(j.calibration,"nao-aplicada");
  j.durationS=30;j.rateHz=500;j.rangeG=2;j.delayS=5;j.intervalS=10;j.repetition=1;j.repetitions=1;j.quiet=false;return j;
}
bool integerArg(const char *key,int64_t lo,int64_t hi,int64_t &out,int64_t fallback) {
  if(!server.hasArg(key)){out=fallback;return true;}
  String s=server.arg(key);char *end=nullptr;const char *p=s.c_str();
  if(!*p)return false;long long value=strtoll(p,&end,10);
  if(*end||value<lo||value>hi)return false;out=value;return true;
}
bool labelArg(const char *key,char *out,size_t capacity,const char *fallback) {
  String s=server.hasArg(key)?server.arg(key):String(fallback);
  if(!safeId(s.c_str(),capacity-1))return false;s.toCharArray(out,capacity);return true;
}
bool parseJob(Job &j,String &error) {
  Job d=defaults();j=d;int64_t v;
  if(!labelArg("sensor",j.sensor,sizeof(j.sensor),d.sensor)||!labelArg("montagem",j.mount,sizeof(j.mount),d.mount)||
     !labelArg("ensaio",j.experiment,sizeof(j.experiment),d.experiment)||!labelArg("posicao",j.position,sizeof(j.position),d.position)||
     !labelArg("calibracao_id",j.calibration,sizeof(j.calibration),d.calibration)){error="Identificadores: use letras ASCII, numeros, _ e -, sem espacos.";return false;}
  String ref=server.hasArg("referencial")?server.arg("referencial"):"conjunto";
  if(ref!="conjunto"&&ref!="sensor"){error="Referencial invalido.";return false;}ref.toCharArray(j.reference,sizeof(j.reference));
  if(!integerArg("duracao_s",1,MAX_DURATION_S,v,d.durationS)){error="Duracao invalida (1 a 21600 s).";return false;}j.durationS=v;
  if(!integerArg("taxa",250,500,v,d.rateHz)||(v!=250&&v!=500)){error="Taxa deve ser 250 ou 500.";return false;}j.rateHz=v;
  if(!integerArg("faixa",2,8,v,d.rangeG)||(v!=2&&v!=4&&v!=8)){error="Faixa deve ser 2, 4 ou 8.";return false;}j.rangeG=v;
  if(!integerArg("atraso_s",0,3600,v,d.delayS)){error="Atraso invalido.";return false;}j.delayS=v;
  if(!integerArg("intervalo_s",0,3600,v,d.intervalS)){error="Intervalo invalido.";return false;}j.intervalS=v;
  if(!integerArg("repeticao",1,999,v,d.repetition)){error="Repeticao invalida.";return false;}j.repetition=v;
  if(!integerArg("repeticoes",1,MAX_REPETITIONS,v,d.repetitions)){error="Quantidade de repeticoes invalida.";return false;}j.repetitions=v;
  if(j.repetition+j.repetitions-1>999){error="Ultima repeticao excede 999.";return false;}
  String radio=server.hasArg("radio")?server.arg("radio"):"ativo";
  if(radio!="ativo"&&radio!="desligado"){error="Radio deve ser ativo ou desligado.";return false;}j.quiet=radio=="desligado";
  String note=server.arg("nota");if(note.length()>240){error="Nota excede 240 bytes UTF-8.";return false;}note.toCharArray(j.note,sizeof(j.note));
  return true;
}
void sendJson(int code,const String &json){server.sendHeader("Cache-Control","no-store");server.send(code,"application/json; charset=utf-8",json);}
void fail(int code,const String &error){sendJson(code,"{\"erro\":"+quote(error)+"}");}
String statusJson() {
  Runtime s=snapshot();
  return "{\"estado\":"+quote(phaseName(s.phase))+",\"ocupado\":"+String(s.busy?"true":"false")+
    ",\"run_id\":"+quote(s.run)+",\"request_id\":"+quote(lastRequest)+",\"motivo\":"+quote(reasonName(s.reason))+
    ",\"repeticao\":"+String(s.repetition)+",\"registros_concluidos\":"+String(s.seriesDone)+
    ",\"registros_programados\":"+String(s.seriesTotal)+",\"amostras_adquiridas\":"+String(s.acquired)+
    ",\"amostras_gravadas\":"+String(s.written)+",\"buffer_pico\":"+String(s.queuePeak)+
    ",\"perdas_limite_inferior\":"+String(s.lostLowerBound)+",\"erros_spi\":"+String(s.spiErrors)+
    ",\"arquivo_finalizado\":"+String(s.rawFinalized?"true":"false")+
    ",\"tempo_registrado_s\":"+String(s.startUs>0&&s.lastSampleUs>s.startUs?(s.lastSampleUs-s.startUs)/1000000.0:0,3)+
    ",\"sequencia_ids\":"+(s.busy?String("[]"):lastSeriesIds.length()?lastSeriesIds:String("[]"))+"}";
}
bool enqueueJob(const Job &j) {
  if(!tasksReady||!cardReady||!sensorReady||snapshot().busy)return false;
  stopRequested=false;lastRequest=j.request;lastSeriesIds="[]";
  portENTER_CRITICAL(&stateMux);runtime.busy=true;runtime.phase=Phase::PREPARING;runtime.reason=Reason::NONE;portEXIT_CRITICAL(&stateMux);
  if(xQueueSend(jobQueue,&j,0)!=pdTRUE){portENTER_CRITICAL(&stateMux);runtime.busy=false;runtime.phase=Phase::ERROR;portEXIT_CRITICAL(&stateMux);return false;}
  return true;
}
String filePath(const String &dir,const String &kind) {
  if(kind=="bin")return SD.exists((dir+"/raw.bin").c_str())?dir+"/raw.bin":dir+"/raw.bin.part";
  if(kind=="meta")return dir+"/meta.json";if(kind=="manifest")return dir+"/manifest.json";
  if(kind=="log")return dir+"/events.log";return "";
}
void handleFiles() {
  if(snapshot().busy){fail(409,"Aguarde o fim da sequencia para acessar o cartao.");return;}
  int64_t offset;if(!integerArg("offset",0,1000000,offset,0)){fail(400,"Offset invalido.");return;}
  File root=SD.open("/ensaios");if(!root){fail(503,"Cartao indisponivel.");return;}
  String out="{\"arquivos\":[";unsigned index=0,count=0;bool more=false;
  for(File f=root.openNextFile();f;f=root.openNextFile()) {
    if(f.isDirectory()) {
      if(index++<unsigned(offset)){f.close();continue;}
      if(count==50){more=true;f.close();break;}
      String id=f.name();int slash=id.lastIndexOf('/');if(slash>=0)id=id.substring(slash+1);
      if(safeId(id.c_str(),31)){if(count++)out+=',';out+="{\"id\":"+quote(id)+",\"finalizado\":"+
        String(SD.exists((directoryFor(id.c_str())+"/manifest.json").c_str())?"true":"false")+"}";}
    }
    f.close();
  }
  root.close();out+="],\"mais\":"+String(more?"true":"false")+",\"proximo_offset\":"+String(offset+count)+"}";sendJson(200,out);
}
void handleDownload() {
  if(snapshot().busy){fail(409,"Download bloqueado durante a sequencia.");return;}
  String run=server.arg("run");if(!safeId(run.c_str(),31)){fail(400,"Run invalido.");return;}
  String path=filePath(directoryFor(run.c_str()),server.arg("kind"));if(!path.length()){fail(400,"Tipo invalido.");return;}
  File f=SD.open(path.c_str(),FILE_READ);if(!f){fail(404,"Arquivo nao encontrado.");return;}
  int64_t offset;if(!integerArg("offset",0,INT32_MAX,offset,0)||uint64_t(offset)>f.size()){f.close();fail(416,"Offset fora do arquivo.");return;}
  size_t total=f.size(),remaining=total-size_t(offset);f.seek(offset);
  server.sendHeader("Content-Disposition","attachment; filename=\""+run+"_"+path.substring(path.lastIndexOf('/')+1)+"\"");
  server.sendHeader("Accept-Ranges","bytes");
  if(offset)server.sendHeader("Content-Range","bytes "+String(offset)+"-"+String(total-1)+"/"+String(total));
  server.setContentLength(remaining);server.send(offset?206:200,"application/octet-stream","");
  auto client=server.client();uint8_t buffer[4096];
  while(remaining&&client.connected()) {
    size_t n=f.read(buffer,remaining<sizeof(buffer)?remaining:sizeof(buffer));if(!n)break;
    size_t sent=0;int64_t began=esp_timer_get_time();
    while(sent<n&&client.connected()){size_t k=client.write(buffer+sent,n-sent);if(k){sent+=k;began=esp_timer_get_time();}else if(esp_timer_get_time()-began>5000000)break;delay(1);}
    if(sent!=n)break;remaining-=n;delay(1);
  }
  f.close();
}
String extractString(const String &json,const char *key) {
  String marker=quote(key);int pos=json.indexOf(marker);if(pos<0)return "";
  pos=json.indexOf(':',pos+marker.length());if(pos<0)return "";
  int first=json.indexOf('"',pos+1);if(first<0)return "";int last=json.indexOf('"',first+1);
  return last>first?json.substring(first+1,last):"";
}
void storeAutostart(const Job &j,bool enable) {
  preferences.putBool("auto",false); // A flag e escrita por ultimo.
  if(enable) {
    preferences.putBytes("job",&j,sizeof(j));preferences.putUInt("jobver",3);preferences.putBool("auto",true);
  }
}
void routes() {
  server.on("/",HTTP_GET,[]{server.send_P(200,"text/html; charset=utf-8",WEB_UI);});
  server.on("/api/status",HTTP_GET,[]{sendJson(200,statusJson());});
  server.on("/api/info",HTTP_GET,[]{
    char ids[80];snprintf(ids,sizeof(ids),"[\"0x%02X\",\"0x%02X\",\"0x%02X\",\"0x%02X\"]",identity[0],identity[1],identity[2],identity[3]);
    sendJson(200,"{\"firmware\":"+quote(FW_VERSION)+",\"sensor\":\"ADXL355\",\"ids_ad_mst_part_rev\":"+String(ids)+
      ",\"sensor_pronto\":"+String(sensorReady?"true":"false")+",\"sd_pronto\":"+String(cardReady?"true":"false")+
      ",\"tarefas_prontas\":"+String(tasksReady?"true":"false")+",\"sd_total_bytes\":"+u64(cardCapacity)+
      ",\"sd_livre_bytes_ultima_consulta\":"+u64(cardFree)+",\"heap_livre\":"+String(ESP.getFreeHeap())+
      ",\"psram_bytes\":"+String(ESP.getPsramSize())+",\"autostart_armado\":"+String(preferences.getBool("auto",false)?"true":"false")+
      ",\"ip\":"+quote(WiFi.softAPIP().toString())+",\"sincronismo_entre_nos_validado\":false}");
  });
  server.on("/api/clock",HTTP_POST,[]{
    if(snapshot().busy){fail(409,"Relogio so pode ser atualizado em repouso.");return;}
    int64_t v;if(!integerArg("epoch_ms",1577836800000LL,4102444800000LL,v,0)){fail(400,"epoch_ms invalido.");return;}
    clockEpochMs=v;clockBootUs=esp_timer_get_time();clockKnown=true;
    sendJson(200,"{\"hora_recebida\":true,\"sincronismo_entre_nos_validado\":false}");
  });
  server.on("/api/start",HTTP_POST,[]{
    String request=server.arg("request_id");if(!safeId(request.c_str(),64)){fail(400,"Informe request_id unico (ate 64 caracteres).");return;}
    if(request==lastRequest){sendJson(200,statusJson());return;}
    if(snapshot().busy){fail(409,"Uma sequencia ja esta em andamento.");return;}
    Job j;String error;if(!parseJob(j,error)){fail(400,error);return;}request.toCharArray(j.request,sizeof(j.request));
    if(!enqueueJob(j)){fail(503,"Sensor, cartao ou tarefas indisponiveis; consulte INFO.");return;}sendJson(202,statusJson());
  });
  server.on("/api/stop",HTTP_POST,[]{if(snapshot().busy)stopRequested=true;sendJson(200,"{\"parada_solicitada\":true}");});
  server.on("/api/autostart",HTTP_POST,[]{
    if(snapshot().busy){fail(409,"Aguarde o fim da sequencia.");return;}
    if(server.arg("habilitar")=="0"){Job j=defaults();storeAutostart(j,false);sendJson(200,"{\"autostart_armado\":false}");return;}
    Job j;String error;if(!parseJob(j,error)){fail(400,error);return;}
    storeAutostart(j,true);sendJson(200,"{\"autostart_armado\":true,\"execucao\":\"uma_vez_na_proxima_partida\"}");
  });
  server.on("/api/files",HTTP_GET,handleFiles);server.on("/api/download",HTTP_GET,handleDownload);
  server.on("/api/ack",HTTP_POST,[]{
    if(snapshot().busy){fail(409,"Aguarde o fim da sequencia.");return;}
    String run=server.arg("run"),hash=server.arg("sha256");if(!safeId(run.c_str(),31)||hash.length()!=64){fail(400,"Run/hash invalido.");return;}
    String dir=directoryFor(run.c_str());File f=SD.open((dir+"/manifest.json").c_str(),FILE_READ);if(!f){fail(404,"Manifesto ausente.");return;}
    String m=f.readString();f.close();if(extractString(m,"raw_sha256")!=hash){fail(409,"SHA-256 nao corresponde ao arquivo local.");return;}
    if(!writeText(dir+"/recebido.json","{\"sha256\":"+quote(hash)+",\"ack_boot_us\":"+i64(esp_timer_get_time())+",\"copia_local_mantida\":true}")){fail(500,"Nao foi possivel registrar a confirmacao.");return;}
    sendJson(200,"{\"recebimento_registrado\":true,\"copia_local_mantida\":true}");
  });
  server.onNotFound([]{fail(404,"Recurso inexistente.");});
}
void startRadio() {
  WiFi.mode(WIFI_AP);WiFi.softAPConfig(IPAddress(192,168,4,1),IPAddress(192,168,4,1),IPAddress(255,255,255,0));
  apStarted=WiFi.softAP(AP_SSID,AP_PASSWORD);radioIsOff=false;server.begin();
  Serial.printf("#WIFI,ssid=%s,ip=192.168.4.1,ok=%u\n",AP_SSID,unsigned(apStarted));
}
void nodeSetup() {
  Serial.begin(SERIAL_BAUD); // Nao usar while(!Serial): o no funciona sem computador.
  preferences.begin("a355v3",false);bootCount=preferences.getUInt("boots",0)+1;preferences.putUInt("boots",bootCount);bootRandom=esp_random();
  pinMode(SENSOR_CS,OUTPUT);digitalWrite(SENSOR_CS,HIGH);pinMode(CARD_CS,OUTPUT);digitalWrite(CARD_CS,HIGH);pinMode(SENSOR_DRDY,INPUT);
  sensorBus.begin(SENSOR_SCK,SENSOR_MISO,SENSOR_MOSI,SENSOR_CS);sensorReady=initializeSensor();
  cardBus.begin(CARD_SCK,CARD_MISO,CARD_MOSI,CARD_CS);cardReady=SD.begin(CARD_CS,cardBus,CARD_SPI_HZ);
  if(cardReady){if(!SD.exists("/ensaios"))cardReady=SD.mkdir("/ensaios");cardCapacity=SD.totalBytes();uint64_t used=SD.usedBytes();cardFree=cardCapacity>used?cardCapacity-used:0;}
  recordQueue=xQueueCreate(SAMPLE_QUEUE_LENGTH,sizeof(RawRecord));jobQueue=xQueueCreate(1,sizeof(Job));
  if(recordQueue&&jobQueue){
    BaseType_t a=xTaskCreatePinnedToCore(acquisitionTask,"a355_acq",6144,nullptr,5,&acquisitionHandle,1);
    BaseType_t b=xTaskCreatePinnedToCore(storageTask,"a355_sd",14336,nullptr,2,&storageHandle,0);tasksReady=a==pdPASS&&b==pdPASS;
  }
  attachInterrupt(digitalPinToInterrupt(SENSOR_DRDY),dataReady,RISING);routes();
  bool autoFlag=preferences.getBool("auto",false);Job j{};bool loaded=false;
  if(autoFlag){preferences.putBool("auto",false);loaded=preferences.getUInt("jobver",0)==3&&preferences.getBytesLength("job")==sizeof(Job)&&preferences.getBytes("job",&j,sizeof(j))==sizeof(j);}
  if(loaded){snprintf(j.request,sizeof(j.request),"boot-%08lX-%08lX",(unsigned long)bootCount,(unsigned long)bootRandom);enqueueJob(j);}
  if(!(loaded&&j.quiet&&snapshot().busy))startRadio();else radioIsOff=true;
  Serial.printf("#READY,firmware=%s,sensor_ok=%u,ids=%02X/%02X/%02X/%02X,sd_ok=%u,tarefas_ok=%u\n",FW_VERSION,unsigned(sensorReady),identity[0],identity[1],identity[2],identity[3],unsigned(cardReady),unsigned(tasksReady));
}
void nodeLoop() {
  if(radioOffRequested&&!radioIsOff){radioOffRequested=false;server.stop();WiFi.mode(WIFI_OFF);apStarted=false;radioIsOff=true;}
  if(restoreRadioRequested){restoreRadioRequested=false;radioOffRequested=false;startRadio();}
  if(apStarted)server.handleClient();
  static char command[48];static unsigned length=0;
  while(Serial.available()) {
    char c=Serial.read();if(c=='\r')continue;
    if(c=='\n'){command[length]=0;if(!strcmp(command,"STOP"))stopRequested=true;
      else if(!strcmp(command,"INFO"))Serial.printf("#INFO,firmware=%s,devid_ad=0x%02X,devid_mst=0x%02X,partid=0x%02X,revid=0x%02X,sensor_pronto=%u,sd_pronto=%u,tarefas_prontas=%u\n",FW_VERSION,identity[0],identity[1],identity[2],identity[3],unsigned(sensorReady),unsigned(cardReady),unsigned(tasksReady));
      else if(!strcmp(command,"STATUS"))Serial.println(statusJson());
      else if(!strcmp(command,"HELP"))Serial.println("INFO; STATUS; STOP. Controle e downloads: http://192.168.4.1");
      length=0;
    }else if(length<sizeof(command)-1)command[length++]=c;
  }
  delay(2);
}
