#pragma once
#include "FreeRTOS.h"
inline unsigned ulTaskNotifyTake(BaseType_t,TickType_t){return 0;}inline void vTaskDelay(TickType_t){}
inline void vTaskNotifyGiveFromISR(TaskHandle_t,BaseType_t*){}inline void xTaskNotifyGive(TaskHandle_t){}
inline BaseType_t xTaskCreatePinnedToCore(void(*)(void*),const char*,unsigned,void*,unsigned,TaskHandle_t*,int){return pdPASS;}
