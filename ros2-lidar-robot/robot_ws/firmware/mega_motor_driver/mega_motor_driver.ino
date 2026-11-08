/*
 * mega_motor_driver : Raspberry Pi  <->  Arduino Mega 2560  <->  H-bridge  <->  motors
 *
 * The Pi sends the wanted PWM of the LEFT and RIGHT side (the two motors of one side are wired
 * in parallel on one H-bridge channel). The Mega only drives the pins; speed control, odometry,
 * SLAM and navigation run on the Pi.
 *
 * Serial link: USB cable Pi <-> Mega, 115200 baud, text lines ending with '\n'.
 *   Pi -> Mega   "M <left> <right>"   PWM -255..255, the sign is the direction.  e.g. "M 120 -120"
 *                "S"                  stop both sides
 *                "P"                  ping, answer "PONG"
 *                "Z"                  reset the encoder counters (only if ENCODERS is 1)
 *   Mega -> Pi   "# mega_motor_driver ready"       once, after reset
 *                "T <ticks_left> <ticks_right>"    every 50 ms (only if ENCODERS is 1)
 *                "? <line>"                        for a line it could not understand
 *
 * Safety: if no valid "M" line arrives for WATCHDOG_MS, the motors stop (cable unplugged,
 * Pi crashed, ROS stopped...).
 *
 * >>> Edit the CONFIG section below to match YOUR wiring. <<<
 */
#include <Arduino.h>
#include <stdlib.h>

// ============================== CONFIG ==============================
// H-bridge type:
//   1 = EN + IN1 + IN2 per side   (L298N, L293D, TB6612, VNH2SP30 ...)
//   2 = RPWM + LPWM per side      (BTS7960 / IBT-2, DRV8871 ...), with optional R_EN/L_EN pins
#define DRIVER_TYPE 1

// LEFT side. Type 1: IN1, IN2 = direction pins, PWM = ENA (must be a PWM pin).
//            Type 2: PWM = RPWM (forward), PWM2 = LPWM (reverse); IN1/IN2 = R_EN/L_EN (set HIGH).
#define L_IN1   22
#define L_IN2   23
#define L_PWM   5      // Mega PWM pins: 2..13 and 44..46
#define L_PWM2  4      // only used by type 2

// RIGHT side
#define R_IN1   24
#define R_IN2   25
#define R_PWM   6
#define R_PWM2  7      // only used by type 2

// Safety: stop after this long without a valid "M" command
#define WATCHDOG_MS 400

// Optional wheel encoders (quadrature). 0 = no encoders (default).
#define ENCODERS 0
#define ENC_L_A 18     // must be an interrupt pin of the Mega: 2, 3, 18, 19, 20, 21
#define ENC_L_B 31
#define ENC_R_A 19
#define ENC_R_B 33
// ====================================================================

static unsigned long lastCmdMs = 0;
static bool stopped = true;
static char lineBuf[40];
static uint8_t lineLen = 0;

#if ENCODERS
static volatile long encL = 0, encR = 0;
static void isrL() { if (digitalRead(ENC_L_B)) encL++; else encL--; }
static void isrR() { if (digitalRead(ENC_R_B)) encR++; else encR--; }
static unsigned long lastTickMs = 0;
#endif

static void driveSide(uint8_t in1, uint8_t in2, uint8_t pwm, uint8_t pwm2, int duty) {
#if DRIVER_TYPE == 1
  (void)pwm2;
  if (duty > 0)      { digitalWrite(in1, HIGH); digitalWrite(in2, LOW);  analogWrite(pwm, duty); }
  else if (duty < 0) { digitalWrite(in1, LOW);  digitalWrite(in2, HIGH); analogWrite(pwm, -duty); }
  else               { digitalWrite(in1, LOW);  digitalWrite(in2, LOW);  analogWrite(pwm, 0); }
#else
  (void)in1; (void)in2;
  analogWrite(pwm,  duty > 0 ? duty : 0);
  analogWrite(pwm2, duty < 0 ? -duty : 0);
#endif
}

static void setMotors(int left, int right) {
  left  = constrain(left,  -255, 255);
  right = constrain(right, -255, 255);
  driveSide(L_IN1, L_IN2, L_PWM, L_PWM2, left);
  driveSide(R_IN1, R_IN2, R_PWM, R_PWM2, right);
  stopped = (left == 0 && right == 0);
}

static void handleLine(char* s) {
  while (*s == ' ') s++;
  if (*s == '\0') return;
  switch (*s) {
    case 'M': {
      char* p1;
      char* p2;
      long l = strtol(s + 1, &p1, 10);
      if (p1 == s + 1) break;
      long r = strtol(p1, &p2, 10);
      if (p2 == p1) break;
      setMotors((int)l, (int)r);
      lastCmdMs = millis();
      return;
    }
    case 'S':
      setMotors(0, 0);
      lastCmdMs = millis();
      return;
    case 'P':
      Serial.println("PONG");
      return;
    case 'Z':
#if ENCODERS
      noInterrupts(); encL = 0; encR = 0; interrupts();
#endif
      return;
    default:
      break;
  }
  Serial.print("? ");
  Serial.println(s);
}

void setup() {
  pinMode(L_IN1, OUTPUT); pinMode(L_IN2, OUTPUT); pinMode(L_PWM, OUTPUT);
  pinMode(R_IN1, OUTPUT); pinMode(R_IN2, OUTPUT); pinMode(R_PWM, OUTPUT);
#if DRIVER_TYPE == 2
  pinMode(L_PWM2, OUTPUT); pinMode(R_PWM2, OUTPUT);
  digitalWrite(L_IN1, HIGH); digitalWrite(L_IN2, HIGH);   // R_EN / L_EN
  digitalWrite(R_IN1, HIGH); digitalWrite(R_IN2, HIGH);
#endif
  setMotors(0, 0);
#if ENCODERS
  pinMode(ENC_L_A, INPUT_PULLUP); pinMode(ENC_L_B, INPUT_PULLUP);
  pinMode(ENC_R_A, INPUT_PULLUP); pinMode(ENC_R_B, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(ENC_L_A), isrL, RISING);
  attachInterrupt(digitalPinToInterrupt(ENC_R_A), isrR, RISING);
#endif
  Serial.begin(115200);
  Serial.println("# mega_motor_driver ready");
  lastCmdMs = millis();
}

void loop() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      lineBuf[lineLen] = '\0';
      handleLine(lineBuf);
      lineLen = 0;
    } else if (lineLen < sizeof(lineBuf) - 1) {
      lineBuf[lineLen++] = c;
    } else {
      lineLen = 0;                       // line too long: drop it
    }
  }

  if (!stopped && (millis() - lastCmdMs) > WATCHDOG_MS) {
    setMotors(0, 0);                     // no command from the Pi: stop
  }

#if ENCODERS
  if (millis() - lastTickMs >= 50) {
    lastTickMs = millis();
    long l, r;
    noInterrupts(); l = encL; r = encR; interrupts();
    Serial.print("T "); Serial.print(l); Serial.print(' '); Serial.println(r);
  }
#endif
}
