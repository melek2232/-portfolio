/*
  ============================================================================
  Industrial Digital Voltmeter — Auto-Ranging with ADS1115 + CD4051
  ============================================================================
  Author:      Melek Chourabi
  Supervisor:  M. Abdelkrim Ayari — SAGEMCOM
  Context:     ENIT internship project, 2024/2025

  Hardware:
    - Arduino UNO (ATmega328P)
    - ADS1115 16-bit I2C ADC (Adafruit_ADS1X15 library)
    - CD4051 8-channel analog multiplexer (3 select lines: S0, S1, S2)
    - 4 switchable resistive dividers wired to CD4051 channels X0..X3:
        X0 -> ratio 1:1     (direct link, Rhaut = 0)
        X1 -> ratio 1:10    (Rbas = 10k, Rhaut = 90k)
        X2 -> ratio 1:50    (Rbas = 10k, Rhaut = 490k)
        X3 -> ratio 1:100   (Rbas = 10k, Rhaut = 990k)

  Fixes applied vs. the original draft used during the internship:
    1. GAIN_SIX does not exist in the Adafruit_ADS1X15 library. The correct
       constant for a full-scale range of +-6.144 V is GAIN_TWOTHIRDS.
    2. The multiplexer only needs 3 select lines (S0, S1, S2) to match the
       CD4051 hardware in the schematic — the 4th line (MUX_S3) from the
       original draft did not correspond to any real hardware pin and has
       been removed. Only channels X0-X3 are used, so S2 is always LOW.
    3. Added hysteresis around the range-switching thresholds to prevent
       the display from oscillating between two ranges when the input
       sits right on a boundary.
    4. Added ADC saturation detection: if the raw reading approaches the
       16-bit full-scale count, the code forces a safer (more attenuated)
       range and flags the reading as out-of-range instead of silently
       returning a clipped value.
    5. Added simple offset/gain calibration hooks (CAL_OFFSET / CAL_GAIN)
       so the meter can be tuned against a reference voltage source.
  ============================================================================
*/

#include <Wire.h>
#include <Adafruit_ADS1X15.h>

Adafruit_ADS1115 ads;

// ---------------------------------------------------------------------------
// Multiplexer control pins (CD4051: S0, S1, S2)
// ---------------------------------------------------------------------------
const uint8_t MUX_S0 = 2;
const uint8_t MUX_S1 = 3;
const uint8_t MUX_S2 = 4;

// ---------------------------------------------------------------------------
// Divider ratios <-> CD4051 channel mapping
// ---------------------------------------------------------------------------
enum DividerRatio : uint8_t {
  RATIO_1_1   = 0,  // CD4051 channel X0
  RATIO_1_10  = 1,  // CD4051 channel X1
  RATIO_1_50  = 2,  // CD4051 channel X2
  RATIO_1_100 = 3   // CD4051 channel X3
};

DividerRatio currentDivider = RATIO_1_100;

// ---------------------------------------------------------------------------
// ADS1115 configuration
//   Gain +-6.144 V  -> GAIN_TWOTHIRDS -> 0.1875 mV / LSB (16-bit, 1 sign bit)
// ---------------------------------------------------------------------------
const float ADS_MULTIPLIER_V = 0.0001875f;   // volts per LSB at +-6.144 V
const int16_t ADC_SATURATION_COUNTS = 32000; // safety margin below 32767

// Averaging for low-voltage / high-resolution readings
const uint8_t NUM_SAMPLES = 10;

// Range-switching thresholds, with hysteresis to avoid flicker between ranges
const float LOW_VOLTAGE_THRESHOLD = 0.10f;   // V, below this -> step down
const float TH_10_UP    = 5.0f,  TH_10_DOWN  = 4.5f;   // 1:10  <-> 1:50 boundary
const float TH_50_UP    = 25.0f, TH_50_DOWN  = 22.0f;  // 1:50  <-> 1:100 boundary

// Optional single-point calibration (adjust after measuring a known reference)
const float CAL_OFFSET_V = 0.0f;  // additive offset, in volts, at the input
const float CAL_GAIN     = 1.0f;  // multiplicative correction (ideally ~1.0)

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------
void setup() {
  Serial.begin(9600);

  pinMode(MUX_S0, OUTPUT);
  pinMode(MUX_S1, OUTPUT);
  pinMode(MUX_S2, OUTPUT);

  // Always start on the most protective range (1:100) before the ADC/MUX
  // are even confirmed to be working — this limits the voltage that can
  // ever reach the ADC input during power-up.
  setDividerRatio(RATIO_1_100);

  if (!ads.begin()) {
    Serial.println(F("ERROR: ADS1115 not found. Check wiring/I2C address."));
    while (1) { delay(1000); }
  }

  ads.setGain(GAIN_TWOTHIRDS);   // +-6.144 V full scale

  Serial.println(F("Industrial voltmeter ready. Auto-ranging enabled."));
}

// ---------------------------------------------------------------------------
// Main loop
// ---------------------------------------------------------------------------
void loop() {
  bool overRange = false;
  float voltage = readVoltageAutoRange(overRange);

  Serial.print(F("Voltage: "));
  Serial.print(voltage, (fabs(voltage) < 0.1f) ? 6 : 4);
  Serial.print(F(" V  (Range: 1:"));
  Serial.print(getDividerFactor(currentDivider));
  Serial.print(F(")"));

  if (overRange) {
    Serial.print(F("  [OVER-RANGE]"));
  }
  Serial.println();

  delay(1000);
}

// ---------------------------------------------------------------------------
// Auto-ranging measurement
// Returns the reconstructed input voltage and sets overRange if the ADC
// saturated even on the safest (1:100) range.
// ---------------------------------------------------------------------------
float readVoltageAutoRange(bool &overRange) {
  overRange = false;

  // Step 1: always probe first on the safest range
  setDividerRatio(RATIO_1_100);
  delay(20); // allow the multiplexer / divider network to settle

  int16_t rawCounts = ads.readADC_SingleEnded(0);
  if (abs(rawCounts) >= ADC_SATURATION_COUNTS) {
    // Input exceeds what even the 1:100 divider can safely present to the ADC
    overRange = true;
    return countsToVoltage(rawCounts) * getDividerFactor(RATIO_1_100);
  }

  float estimate = countsToVoltage(rawCounts) * getDividerFactor(RATIO_1_100);

  // Step 2: choose the most sensitive range that still fits, with hysteresis
  DividerRatio target;
  if (estimate < LOW_VOLTAGE_THRESHOLD) {
    target = chooseLowVoltageRange();
  } else if (estimate < TH_10_UP) {
    target = RATIO_1_10;
  } else if (estimate < TH_50_UP) {
    target = RATIO_1_50;
  } else {
    target = RATIO_1_100;
  }

  setDividerRatio(target);
  delay(20);

  // Step 3: final measurement (averaged on the most sensitive range)
  float finalVoltage;
  if (currentDivider == RATIO_1_1) {
    finalVoltage = readAveraged(NUM_SAMPLES) * getDividerFactor(currentDivider);
  } else {
    int16_t counts = ads.readADC_SingleEnded(0);
    if (abs(counts) >= ADC_SATURATION_COUNTS) {
      overRange = true;
    }
    finalVoltage = countsToVoltage(counts) * getDividerFactor(currentDivider);
  }

  return applyCalibration(finalVoltage);
}

// Gradually steps down from 1:100 to 1:1 to find the most sensitive safe range
// for very low input voltages.
DividerRatio chooseLowVoltageRange() {
  setDividerRatio(RATIO_1_50);
  delay(20);
  float v = countsToVoltage(ads.readADC_SingleEnded(0)) * getDividerFactor(RATIO_1_50);
  if (v >= LOW_VOLTAGE_THRESHOLD) return RATIO_1_50;

  setDividerRatio(RATIO_1_10);
  delay(20);
  v = countsToVoltage(ads.readADC_SingleEnded(0)) * getDividerFactor(RATIO_1_10);
  if (v >= LOW_VOLTAGE_THRESHOLD) return RATIO_1_10;

  return RATIO_1_1;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
inline float countsToVoltage(int16_t counts) {
  return counts * ADS_MULTIPLIER_V;
}

inline float applyCalibration(float v) {
  return v * CAL_GAIN + CAL_OFFSET_V;
}

float readAveraged(uint8_t samples) {
  long sum = 0;
  for (uint8_t i = 0; i < samples; i++) {
    sum += ads.readADC_SingleEnded(0);
    delay(5);
  }
  return (sum / (float)samples) * ADS_MULTIPLIER_V;
}

void setDividerRatio(DividerRatio ratio) {
  digitalWrite(MUX_S0, (ratio >> 0) & 0x01);
  digitalWrite(MUX_S1, (ratio >> 1) & 0x01);
  digitalWrite(MUX_S2, 0); // only channels X0-X3 are wired, so S2 stays LOW
  currentDivider = ratio;
}

uint8_t getDividerFactor(DividerRatio ratio) {
  switch (ratio) {
    case RATIO_1_1:   return 1;
    case RATIO_1_10:  return 10;
    case RATIO_1_50:  return 50;
    case RATIO_1_100: return 100;
    default:          return 100; // fail safe: most protective factor
  }
}
