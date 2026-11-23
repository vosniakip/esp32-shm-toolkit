#pragma once
#include "Arduino.h"
#define WIFI_OFF 0
#define WIFI_AP 2
struct IPAddress{IPAddress(int=0,int=0,int=0,int=0){}String toString(){return "0.0.0.0";}};
struct NetworkClient{bool connected(){return false;}size_t write(const uint8_t*,size_t n){return n;}};
struct WiFiMock{void mode(int){}bool softAPConfig(IPAddress,IPAddress,IPAddress){return true;}bool softAP(const char*,const char*){return true;}IPAddress softAPIP(){return {};}};extern WiFiMock WiFi;
