// Minimal Arduino API stubs so the sketch can be compiled and tested on a PC (g++).
#pragma once
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <poll.h>
#include <unistd.h>
#include <time.h>

#define HIGH 1
#define LOW 0
#define OUTPUT 1
#define INPUT_PULLUP 2
#define constrain(x, a, b) ((x) < (a) ? (a) : ((x) > (b) ? (b) : (x)))

#ifndef HOST_FAKE_TIME
unsigned long millis();
#else
extern unsigned long fake_ms;
inline unsigned long millis() { return fake_ms; }
#endif

void pinMode(uint8_t pin, uint8_t mode);
void digitalWrite(uint8_t pin, uint8_t v);
int digitalRead(uint8_t pin);
void analogWrite(uint8_t pin, int v);
inline void noInterrupts() {}
inline void interrupts() {}
inline int digitalPinToInterrupt(int p) { return p; }
#define RISING 3
inline void attachInterrupt(int, void (*)(), int) {}

struct HostSerial {
  void begin(long) {}
  int available();
  int read();
  void print(const char* s);
  void print(long v);
  void print(char c);
  void println(const char* s);
  void println(long v);
};
extern HostSerial Serial;
