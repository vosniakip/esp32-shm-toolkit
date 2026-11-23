#pragma once
#include "WiFi.h"
#define HTTP_GET 0
#define HTTP_POST 1
struct WebServer{WebServer(int){}template<class F>void on(const char*,int,F){}template<class F>void onNotFound(F){}
void sendHeader(String,String){}void send(int,const char*,String){}void send_P(int,const char*,const char*){}
void setContentLength(size_t){}void begin(){}void stop(){}void handleClient(){}bool hasArg(const char*){return false;}String arg(const char*){return {};}
NetworkClient client(){return {};}};
