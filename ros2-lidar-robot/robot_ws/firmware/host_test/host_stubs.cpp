#include "Arduino.h"
#include <string>
#include <deque>
#include <map>

int pin_digital[256];
int pin_pwm[256];
std::string serial_out;                 // everything the sketch prints
std::deque<char> serial_in;             // bytes waiting for the sketch
#ifdef HOST_FAKE_TIME
unsigned long fake_ms = 0;
#else
unsigned long millis() {
  timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts);
  return (unsigned long)(ts.tv_sec * 1000UL + ts.tv_nsec / 1000000UL);
}
#endif
void pinMode(uint8_t, uint8_t) {}
void digitalWrite(uint8_t p, uint8_t v) { pin_digital[p] = v; }
int digitalRead(uint8_t p) { return pin_digital[p]; }
void analogWrite(uint8_t p, int v) { pin_pwm[p] = v; }

HostSerial Serial;
#ifdef HOST_STDIN
int HostSerial::available() {
  if (!serial_in.empty()) return (int)serial_in.size();
  pollfd pf = {0, POLLIN, 0};
  if (poll(&pf, 1, 0) > 0 && (pf.revents & POLLIN)) {
    char buf[64]; ssize_t n = ::read(0, buf, sizeof buf);
    for (ssize_t i = 0; i < n; i++) serial_in.push_back(buf[i]);
  }
  return (int)serial_in.size();
}
#else
int HostSerial::available() { return (int)serial_in.size(); }
#endif
int HostSerial::read() { if (serial_in.empty()) return -1; char c = serial_in.front(); serial_in.pop_front(); return (unsigned char)c; }
#ifdef HOST_STDIN
static void emit(const std::string& s) { ssize_t r = ::write(1, s.data(), s.size()); (void)r; }
#else
static void emit(const std::string& s) { serial_out += s; }
#endif
void HostSerial::print(const char* s) { emit(s); }
void HostSerial::print(long v) { emit(std::to_string(v)); }
void HostSerial::print(char c) { emit(std::string(1, c)); }
void HostSerial::println(const char* s) { emit(std::string(s) + "\n"); }
void HostSerial::println(long v) { emit(std::to_string(v) + "\n"); }
