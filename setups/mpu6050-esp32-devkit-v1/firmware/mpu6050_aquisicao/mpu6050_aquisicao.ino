/*
  GY-521 (MPU-6050) + ESP32 DevKit V1
  Firmware unico para todos os ensaios de bancada.

  Ligacoes I2C:
    GY-521 VCC -> ESP32 3V3
    GY-521 GND -> ESP32 GND
    GY-521 SDA -> ESP32 GPIO21
    GY-521 SCL -> ESP32 GPIO22
    GY-521 INT -> ESP32 GPIO27
    GY-521 AD0 -> GND (endereco I2C 0x68)

  Comandos enviados pelo computador:
    INFO               mostra a configuracao
    START,120000       inicia aquisicao por 120000 ms
    START,0            inicia e continua ate receber STOP
    STOP               interrompe a aquisicao

  Linhas de dados:
    D,indice,t_us,ax_raw,ay_raw,az_raw,temp_raw,perdidas_acum,erros_i2c

  Bibliotecas externas: nenhuma. Usa Wire e esp_timer do nucleo ESP32.
*/

#include <Arduino.h>
#include <Wire.h>
#include "esp_timer.h"

// ----------------------------- Pinos -------------------------------------
constexpr int PINO_SDA = 21;
constexpr int PINO_SCL = 22;
constexpr int PINO_INT = 27;

// -------------------------- Comunicacao ---------------------------------
constexpr uint32_t BAUD_SERIAL = 460800;
constexpr uint32_t CLOCK_I2C_HZ = 400000;

// ----------------------- Configuracao do ensaio --------------------------
constexpr uint16_t FS_NOMINAL_HZ = 250;
constexpr uint8_t DIVISOR_AMOSTRAGEM = 3;  // 1000 / (1 + 3) = 250 Hz
constexpr uint8_t DLPF_CONFIG = 2;         // accel: aproximadamente 94 Hz
constexpr uint8_t FAIXA_ACCEL = 0;         // 0 = +/-2 g = 16384 LSB/g
constexpr uint8_t WHO_AM_I_MPU6050 = 0x68;

// -------------------- Registradores do MPU-6050 --------------------------
constexpr uint8_t REG_SMPLRT_DIV = 0x19;
constexpr uint8_t REG_CONFIG = 0x1A;
constexpr uint8_t REG_GYRO_CONFIG = 0x1B;
constexpr uint8_t REG_ACCEL_CONFIG = 0x1C;
constexpr uint8_t REG_INT_PIN_CFG = 0x37;
constexpr uint8_t REG_INT_ENABLE = 0x38;
constexpr uint8_t REG_ACCEL_XOUT_H = 0x3B;
constexpr uint8_t REG_PWR_MGMT_1 = 0x6B;
constexpr uint8_t REG_PWR_MGMT_2 = 0x6C;
constexpr uint8_t REG_WHO_AM_I = 0x75;

uint8_t enderecoMpu = 0x68;
bool sensorPronto = false;

// A interrupcao incrementa apenas um contador. Toda comunicacao I2C e Serial
// fica fora da ISR, evitando travamentos e longos tempos de interrupcao.
volatile uint32_t eventosPendentes = 0;
portMUX_TYPE muxInterrupcao = portMUX_INITIALIZER_UNLOCKED;

bool adquirindo = false;
uint64_t inicioAquisicaoUs = 0;
uint64_t duracaoSolicitadaUs = 0;
uint32_t indiceAmostra = 0;
uint32_t amostrasPerdidas = 0;
uint32_t errosI2c = 0;


void IRAM_ATTR eventoDataReady() {
  portENTER_CRITICAL_ISR(&muxInterrupcao);
  if (eventosPendentes < UINT32_MAX) {
    eventosPendentes++;
  }
  portEXIT_CRITICAL_ISR(&muxInterrupcao);
}


bool escreverRegistrador(uint8_t registrador, uint8_t valor) {
  Wire.beginTransmission(enderecoMpu);
  Wire.write(registrador);
  Wire.write(valor);
  return Wire.endTransmission(true) == 0;
}


bool lerRegistrador(uint8_t registrador, uint8_t &valor) {
  Wire.beginTransmission(enderecoMpu);
  Wire.write(registrador);
  if (Wire.endTransmission(false) != 0) {
    return false;
  }
  size_t recebidos = Wire.requestFrom(enderecoMpu, static_cast<uint8_t>(1), true);
  if (recebidos != 1 || !Wire.available()) {
    return false;
  }
  valor = Wire.read();
  return true;
}


bool lerBloco(uint8_t primeiroRegistrador, uint8_t *destino, size_t quantidade) {
  Wire.beginTransmission(enderecoMpu);
  Wire.write(primeiroRegistrador);
  if (Wire.endTransmission(false) != 0) {
    return false;
  }

  size_t recebidos = Wire.requestFrom(
      enderecoMpu, static_cast<uint8_t>(quantidade), true);
  if (recebidos != quantidade) {
    while (Wire.available()) {
      Wire.read();
    }
    return false;
  }

  for (size_t i = 0; i < quantidade; i++) {
    if (!Wire.available()) {
      return false;
    }
    destino[i] = Wire.read();
  }
  return true;
}


bool localizarMpu() {
  const uint8_t candidatos[] = {0x68, 0x69};
  for (uint8_t candidato : candidatos) {
    Wire.beginTransmission(candidato);
    if (Wire.endTransmission(true) == 0) {
      enderecoMpu = candidato;
      return true;
    }
  }
  return false;
}


bool configurarMpu() {
  // Reinicializacao completa.
  if (!escreverRegistrador(REG_PWR_MGMT_1, 0x80)) return false;
  delay(120);

  // Clock PLL e todos os eixos ativados.
  if (!escreverRegistrador(REG_PWR_MGMT_1, 0x01)) return false;
  delay(10);
  if (!escreverRegistrador(REG_PWR_MGMT_2, 0x00)) return false;

  // No MPU-6050, CONFIG controla o DLPF do acelerometro e do giroscopio.
  // Com DLPF_CONFIG=2, a base e 1 kHz e o acelerometro fica em cerca de 94 Hz.
  if (!escreverRegistrador(REG_CONFIG, DLPF_CONFIG)) return false;
  if (!escreverRegistrador(REG_SMPLRT_DIV, DIVISOR_AMOSTRAGEM)) return false;
  if (!escreverRegistrador(REG_GYRO_CONFIG, 0x00)) return false;
  if (!escreverRegistrador(REG_ACCEL_CONFIG, FAIXA_ACCEL << 3)) return false;

  // Interrupcao Data Ready ativa em pulso alto.
  if (!escreverRegistrador(REG_INT_PIN_CFG, 0x00)) return false;
  if (!escreverRegistrador(REG_INT_ENABLE, 0x01)) return false;
  delay(20);
  return true;
}


void imprimirInformacoes() {
  uint8_t whoAmI = 0xFF;
  bool leituraOk = lerRegistrador(REG_WHO_AM_I, whoAmI);
  bool identidadeOk = leituraOk && whoAmI == WHO_AM_I_MPU6050;
  Serial.printf(
      "#INFO,sensor=MPU6050,endereco=0x%02X,who_am_i=0x%02X,who_ok=%d,fs_nominal_hz=%u,"
      "dt_nominal_us=%.1f,faixa_g=2,sensibilidade_lsb_g=16384,dlpf_hz_aprox=94,"
      "i2c_hz=%lu,baud=%lu\n",
      enderecoMpu,
      whoAmI,
      identidadeOk ? 1 : 0,
      FS_NOMINAL_HZ,
      1000000.0 / FS_NOMINAL_HZ,
      static_cast<unsigned long>(CLOCK_I2C_HZ),
      static_cast<unsigned long>(BAUD_SERIAL));
}


void iniciarAquisicao(uint64_t duracaoMs) {
  portENTER_CRITICAL(&muxInterrupcao);
  eventosPendentes = 0;
  portEXIT_CRITICAL(&muxInterrupcao);

  indiceAmostra = 0;
  amostrasPerdidas = 0;
  errosI2c = 0;
  inicioAquisicaoUs = static_cast<uint64_t>(esp_timer_get_time());
  duracaoSolicitadaUs = duracaoMs * 1000ULL;
  adquirindo = true;

  Serial.printf("#START,duracao_ms=%llu\n",
                static_cast<unsigned long long>(duracaoMs));
}


void finalizarAquisicao(const char *motivo) {
  if (!adquirindo) return;
  adquirindo = false;
  uint64_t duracaoRealUs =
      static_cast<uint64_t>(esp_timer_get_time()) - inicioAquisicaoUs;
  Serial.printf(
      "#END,motivo=%s,amostras=%lu,perdidas=%lu,erros_i2c=%lu,duracao_us=%llu\n",
      motivo,
      static_cast<unsigned long>(indiceAmostra),
      static_cast<unsigned long>(amostrasPerdidas),
      static_cast<unsigned long>(errosI2c),
      static_cast<unsigned long long>(duracaoRealUs));
}


void processarComando() {
  if (!Serial.available()) return;

  String comando = Serial.readStringUntil('\n');
  comando.trim();
  comando.toUpperCase();

  if (comando == "INFO") {
    imprimirInformacoes();
    return;
  }

  if (comando == "STOP") {
    finalizarAquisicao("comando_stop");
    return;
  }

  if (comando.startsWith("START,")) {
    if (!sensorPronto) {
      Serial.println("#FATAL,sensor_nao_pronto");
      return;
    }
    String textoDuracao = comando.substring(6);
    uint64_t duracaoMs = strtoull(textoDuracao.c_str(), nullptr, 10);
    iniciarAquisicao(duracaoMs);
    return;
  }

  Serial.printf("#ERRO,comando_desconhecido=%s\n", comando.c_str());
}


void adquirirSeDisponivel() {
  if (!adquirindo) return;

  uint32_t pendentes = 0;
  portENTER_CRITICAL(&muxInterrupcao);
  pendentes = eventosPendentes;
  eventosPendentes = 0;
  portEXIT_CRITICAL(&muxInterrupcao);

  if (pendentes == 0) return;

  // O registrador guarda apenas a leitura mais recente. Se mais de uma
  // interrupcao ficou pendente, as anteriores nao podem mais ser recuperadas.
  if (pendentes > 1) {
    amostrasPerdidas += pendentes - 1;
  }

  uint8_t bytes[14];
  if (!lerBloco(REG_ACCEL_XOUT_H, bytes, sizeof(bytes))) {
    errosI2c++;
    return;
  }

  int16_t ax = static_cast<int16_t>((bytes[0] << 8) | bytes[1]);
  int16_t ay = static_cast<int16_t>((bytes[2] << 8) | bytes[3]);
  int16_t az = static_cast<int16_t>((bytes[4] << 8) | bytes[5]);
  int16_t temperatura = static_cast<int16_t>((bytes[6] << 8) | bytes[7]);

  uint64_t agoraUs = static_cast<uint64_t>(esp_timer_get_time());
  uint64_t relativoUs = agoraUs - inicioAquisicaoUs;

  char linha[160];
  int tamanho = snprintf(
      linha,
      sizeof(linha),
      "D,%lu,%llu,%d,%d,%d,%d,%lu,%lu\n",
      static_cast<unsigned long>(indiceAmostra),
      static_cast<unsigned long long>(relativoUs),
      ax,
      ay,
      az,
      temperatura,
      static_cast<unsigned long>(amostrasPerdidas),
      static_cast<unsigned long>(errosI2c));
  if (tamanho > 0) {
    Serial.write(reinterpret_cast<const uint8_t *>(linha),
                 static_cast<size_t>(tamanho));
  }
  indiceAmostra++;

  if (duracaoSolicitadaUs > 0 && relativoUs >= duracaoSolicitadaUs) {
    finalizarAquisicao("tempo_concluido");
  }
}


void setup() {
  Serial.begin(BAUD_SERIAL);
  Serial.setTimeout(20);
  delay(1200);

  Wire.begin(PINO_SDA, PINO_SCL);
  Wire.setClock(CLOCK_I2C_HZ);
  Wire.setTimeOut(20);

  pinMode(PINO_INT, INPUT);

  if (!localizarMpu()) {
    Serial.println("#FATAL,mpu6050_nao_encontrado");
    return;
  }

  uint8_t whoAmI = 0xFF;
  if (!lerRegistrador(REG_WHO_AM_I, whoAmI)) {
    Serial.println("#FATAL,falha_leitura_who_am_i");
    return;
  }
  if (whoAmI != WHO_AM_I_MPU6050) {
    Serial.printf("#FATAL,identificacao_incompativel,who_am_i=0x%02X,esperado=0x68\n",
                  whoAmI);
    return;
  }

  if (!configurarMpu()) {
    Serial.println("#FATAL,falha_configuracao_mpu6050");
    return;
  }

  attachInterrupt(digitalPinToInterrupt(PINO_INT), eventoDataReady, RISING);
  sensorPronto = true;
  Serial.println("#READY");
  imprimirInformacoes();
}


void loop() {
  processarComando();
  adquirirSeDisponivel();
}
