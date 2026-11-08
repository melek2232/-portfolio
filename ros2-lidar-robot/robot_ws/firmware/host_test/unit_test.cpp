// Runs the real sketch with fake time and checks pins / replies.
#include "../mega_motor_driver/mega_motor_driver.ino"
#include <string>
#include <deque>
#include <cstdio>
#include <cstdlib>

extern int pin_digital[256];
extern int pin_pwm[256];
extern std::string serial_out;
extern std::deque<char> serial_in;

static int fails = 0;
#define CHECK(cond) do { if (!(cond)) { printf("FAIL line %d: %s\n", __LINE__, #cond); fails++; } } while (0)

static void feed(const char* s) { while (*s) serial_in.push_back(*s++); }
static void run(unsigned long advance_ms) { fake_ms += advance_ms; loop(); }

int main() {
  setup();
  CHECK(serial_out.find("# mega_motor_driver ready") != std::string::npos);
  CHECK(pin_pwm[L_PWM] == 0 && pin_pwm[R_PWM] == 0);

  feed("M 100 -60\n"); run(10);
  CHECK(pin_digital[L_IN1] == 1 && pin_digital[L_IN2] == 0 && pin_pwm[L_PWM] == 100);
  CHECK(pin_digital[R_IN1] == 0 && pin_digital[R_IN2] == 1 && pin_pwm[R_PWM] == 60);

  feed("M 999 -999\r\n"); run(10);                    // clamp + CRLF tolerated
  CHECK(pin_pwm[L_PWM] == 255 && pin_pwm[R_PWM] == 255);
  CHECK(pin_digital[L_IN1] == 1 && pin_digital[R_IN2] == 1);

  feed("M 0 0\n"); run(10);
  CHECK(pin_pwm[L_PWM] == 0 && pin_pwm[R_PWM] == 0 && pin_digital[L_IN1] == 0 && pin_digital[L_IN2] == 0);

  feed("M 80 80\n"); run(10);
  CHECK(pin_pwm[L_PWM] == 80);
  run(WATCHDOG_MS - 50);                              // still alive
  CHECK(pin_pwm[L_PWM] == 80);
  run(100);                                           // watchdog expired
  CHECK(pin_pwm[L_PWM] == 0 && pin_pwm[R_PWM] == 0);

  feed("M 80 80\nS\n"); run(10);                      // explicit stop
  CHECK(pin_pwm[L_PWM] == 0 && pin_pwm[R_PWM] == 0);

  serial_out.clear();
  feed("P\n"); run(1);
  CHECK(serial_out == "PONG\n");

  serial_out.clear();
  feed("hello\nM 5\nM x y\n"); run(1);                // garbage and incomplete commands
  CHECK(serial_out == "? hello\n? M 5\n? M x y\n");
  CHECK(pin_pwm[L_PWM] == 0);                         // nothing moved

  feed("M 50 50 \n"); run(1);                         // trailing space ok
  CHECK(pin_pwm[L_PWM] == 50);
  feed("M 70"); run(1);                               // line not finished yet: no change
  CHECK(pin_pwm[L_PWM] == 50);
  feed(" 70\n"); run(1);
  CHECK(pin_pwm[L_PWM] == 70);

  // very long line is dropped without crashing
  std::string longline(100, 'M'); longline += "\n";
  feed(longline.c_str()); run(1);

  printf(fails ? "UNIT TESTS FAILED (%d)\n" : "unit tests passed\n", fails);
  return fails ? 1 : 0;
}
