import asyncio
import json

from bleak import BleakScanner, BleakClient
import paho.mqtt.client as mqtt

DEVICE_NAME = "Nano33Sensors"

CHARACTERISTIC_UUID = (
    "19b10001-e8f2-537e-4f6c-d104768a1214"
)

MQTT_HOST = "127.0.0.1"
MQTT_PORT = 1883
MQTT_TOPIC = "sensors/nano33"

mqtt_client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2,
    client_id="nano33_sensor_bridge"
)

mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
mqtt_client.loop_start()


def on_sensor_data(sender, data):
    try:
        payload = data.decode("utf-8").strip()
        sensor_data = json.loads(payload)

        result = mqtt_client.publish(
            MQTT_TOPIC,
            json.dumps(sensor_data),
            qos=0
        )

        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print("MQTT published:", payload)
        else:
            print("MQTT publish failed")

    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        print("Invalid sensor message:", error)


async def main():
    while True:
        print("Searching for Nano33Sensors...")

        device = await BleakScanner.find_device_by_name(
            DEVICE_NAME,
            timeout=10
        )

        if device is None:
            print("Arduino not found; retrying...")
            await asyncio.sleep(2)
            continue

        try:
            async with BleakClient(device) as client:
                print("Connected to Arduino!")

                await client.start_notify(
                    CHARACTERISTIC_UUID,
                    on_sensor_data
                )

                print("Forwarding sensor data to MQTT...")

                while client.is_connected:
                    await asyncio.sleep(1)

        except Exception as error:
            print("BLE connection error:", error)

        await asyncio.sleep(2)


try:
    asyncio.run(main())
except KeyboardInterrupt:
    print("Stopping bridge...")
finally:
    mqtt_client.loop_stop()
    mqtt_client.disconnect()