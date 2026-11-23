#pragma once
#include "FreeRTOS.h"
#include <stddef.h>
inline QueueHandle_t xQueueCreate(unsigned,size_t){return nullptr;}inline unsigned uxQueueMessagesWaiting(QueueHandle_t){return 0;}
inline BaseType_t xQueueSend(QueueHandle_t,const void*,TickType_t){return pdTRUE;}inline BaseType_t xQueueReceive(QueueHandle_t,void*,TickType_t){return pdFALSE;}
inline void xQueueReset(QueueHandle_t){}
