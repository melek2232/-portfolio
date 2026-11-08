
#include <ArduinoBLE.h>
#include <Arduino_BMI270_BMM150.h>
#include <Arduino_HS300x.h>
#include <Arduino_LPS22HB.h>
#include <math.h>

// BLE identifiers: must match the Raspberry Pi program
const char* SERVICE_UUID =
    "19b10000-e8f2-537e-4f6c-d104768a1214";

const char* CHARACTERISTIC_UUID =
    "19b10001-e8f2-537e-4f6c-d104768a1214";

// BLE service and JSON characteristic
BLEService sensorService(SERVICE_UUID);

BLEStringCharacteristic sensorCharacteristic(
    CHARACTERISTIC_UUID,
    BLERead | BLENotify,
    180
);

unsigned long lastSend = 0;
const unsigned long SEND_INTERVAL = 1000;

void setup() {
  Serial.begin(115200);

  if (!IMU.begin()) {
    Serial.println("ERROR: IMU initialization failed");
    while (1);
  }

  if (!HS300x.begin()) {
    Serial.println("ERROR: HS300x initialization failed");
    while (1);
  }

  if (!BARO.begin()) {
    Serial.println("ERROR: Barometer initialization failed");
    while (1);
  }

  if (!BLE.begin()) {
    Serial.println("ERROR: BLE initialization failed");
    while (1);
  }

  BLE.setLocalName("Nano33Sensors");
  BLE.setAdvertisedService(sensorService);

  sensorService.addCharacteristic(sensorCharacteristic);
  BLE.addService(sensorService);

  sensorCharacteristic.writeValue("{}");

  BLE.advertise();

  Serial.println("All sensors initialized.");
  Serial.println("BLE device: Nano33Sensors");
  Serial.println("Waiting for Raspberry Pi...");
}

void loop() {
  BLE.poll();

  if (millis() - lastSend < SEND_INTERVAL) {
    return;
  }

  lastSend = millis();

  // Accelerometer values, expressed in g
  float ax = 0.0;
  float ay = 0.0;
  float az = 0.0;

  if (IMU.accelerationAvailable()) {
    IMU.readAcceleration(ax, ay, az);
  }

  // Approximate tilt from gravity
  // Angles are most meaningful when the board is not accelerating.
  float roll = atan2(ay, az) * 180.0 / PI;
  float pitch = atan2(
      -ax,
      sqrt(ay * ay + az * az)
  ) * 180.0 / PI;

  // Temperature and relative humidity
  float temperature = HS300x.readTemperature();
  float humidity = HS300x.readHumidity();

  // Atmospheric pressure in kPa
  float pressure = BARO.readPressure();

  // Approximate altitude in meters
  float altitude = 44330.0 *
      (1.0 - pow(pressure / 101.325, 1.0 / 5.255));

  // Build one JSON message
  String payload = "{";
  payload += "\"ax\":" + String(ax, 3) + ",";
  payload += "\"ay\":" + String(ay, 3) + ",";
  payload += "\"az\":" + String(az, 3) + ",";
  payload += "\"roll_deg\":" + String(roll, 2) + ",";
  payload += "\"pitch_deg\":" + String(pitch, 2) + ",";
  payload += "\"temperature_c\":" + String(temperature, 2) + ",";
  payload += "\"humidity_pct\":" + String(humidity, 2) + ",";
  payload += "\"pressure_kpa\":" + String(pressure, 3) + ",";
  payload += "\"altitude_m\":" + String(altitude, 2);
  payload += "}";

  // Update the BLE characteristic and notify subscribers
  sensorCharacteristic.writeValue(payload);

  // Also print data for debugging in Serial Monitor
  Serial.println(payload);
}
