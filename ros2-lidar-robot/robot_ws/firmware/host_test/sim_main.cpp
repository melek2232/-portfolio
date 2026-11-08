// The real sketch as a PC program on stdin/stdout, used for the end-to-end test with the Pi code.
// Pin changes are logged to the file in $PIN_LOG.
#ifndef HOST_STDIN
#define HOST_STDIN
#endif
#include "../mega_motor_driver/mega_motor_driver.ino"
#include <cstdlib>
#include <cstdio>
#include <unistd.h>
extern int pin_pwm[256];
extern int pin_digital[256];
int main() {
  FILE* log = fopen(getenv("PIN_LOG") ? getenv("PIN_LOG") : "/dev/null", "w");
  setup();
  int last[4] = {-1, -1, -1, -1};
  while (true) {
    loop();
    int cur[4] = {pin_pwm[L_PWM] * (pin_digital[L_IN1] ? 1 : (pin_digital[L_IN2] ? -1 : 0)),
                  pin_pwm[R_PWM] * (pin_digital[R_IN1] ? 1 : (pin_digital[R_IN2] ? -1 : 0)), 0, 0};
    if (cur[0] != last[0] || cur[1] != last[1]) {
      fprintf(log, "%lu %d %d\n", millis(), cur[0], cur[1]); fflush(log);
      last[0] = cur[0]; last[1] = cur[1];
    }
    usleep(1000);
  }
}
