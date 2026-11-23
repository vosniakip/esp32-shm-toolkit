/* Entrada Arduino: implementacao em node.cpp evita prototipos automaticos ambiguos. */
#include <Arduino.h>
void nodeSetup();
void nodeLoop();
void setup() { nodeSetup(); }
void loop() { nodeLoop(); }
