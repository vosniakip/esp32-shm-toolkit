#pragma once
// Interfaces MINIMAS para compilacao de sintaxe no host. NAO simulam o hardware.
#include <stdint.h>
#include <stddef.h>
#include <string>
#include <sstream>
#include <iomanip>
#include <type_traits>
#include <cstring>
#define PROGMEM
#define ARDUINO_ISR_ATTR
#define OUTPUT 1
#define INPUT 0
#define LOW 0
#define HIGH 1
#define RISING 1
class String {
  std::string value;
 public:
  String()=default;String(const char *s):value(s?s:""){}String(const std::string&s):value(s){}String(char c):value(1,c){}
  template<class T,typename std::enable_if<std::is_arithmetic<T>::value,int>::type=0>
  String(T v,int decimals=2){std::ostringstream out;if(std::is_floating_point<T>::value)out<<std::fixed<<std::setprecision(decimals);if constexpr(std::is_integral<T>::value && sizeof(T)==1)out<<+v;else out<<v;value=out.str();}
  size_t length()const{return value.size();}void reserve(size_t n){value.reserve(n);}const char*c_str()const{return value.c_str();}
  char operator[](size_t i)const{return value[i];}String&operator+=(const String&s){value+=s.value;return *this;}
  friend String operator+(const String&a,const String&b){return String(a.value+b.value);}
  friend bool operator==(const String&a,const String&b){return a.value==b.value;}friend bool operator!=(const String&a,const String&b){return !(a==b);}
  int indexOf(char c,int start=0)const{auto p=value.find(c,start);return p==std::string::npos?-1:int(p);}
  int indexOf(const String&s,int start=0)const{auto p=value.find(s.value,start);return p==std::string::npos?-1:int(p);}
  int lastIndexOf(char c)const{auto p=value.rfind(c);return p==std::string::npos?-1:int(p);}
  String substring(int a)const{return String(value.substr(a));}String substring(int a,int b)const{return String(value.substr(a,b-a));}
  void toCharArray(char *p,size_t n)const{if(n){std::strncpy(p,value.c_str(),n-1);p[n-1]=0;}}
};
struct SerialMock{void begin(unsigned){}int available(){return 0;}char read(){return 0;}template<class T>void println(const T&){}int printf(const char*,...) __attribute__((format(printf,2,3)));};
extern SerialMock Serial;
struct ESPMock{unsigned getFreeHeap(){return 0;}unsigned getPsramSize(){return 0;}};extern ESPMock ESP;
inline void delay(unsigned){}inline void pinMode(int,int){}inline void digitalWrite(int,int){}inline int digitalPinToInterrupt(int n){return n;}inline void attachInterrupt(int,void(*)(),int){}
