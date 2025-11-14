import asyncio
import json
import threading
import paho.mqtt.client as mqtt
from bleak import BleakClient, BleakScanner

# UUIDs
SERVICE_UUID = "19b10000-e8f2-537e-4f6c-d104768a1214"
SENSORS_UUID = "19b10001-e8f2-537e-4f6c-d104768a1214"  # Notify (BLE → PC)
CONTROL_UUID = "19b1000a-e8f2-537e-4f6c-d104768a1214"  # Write (PC → BLE)

# MQTT settings
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
TOPIC_SENSOR = "sensor/data"
TOPIC_CONTROL = "control"

# Globals
ble_client = None
loop = None  # asyncio loop reference

mqtt_client = mqtt.Client()

# ---------- Parse Sensor Data ----------
def parse_sensor_data(text):
    parts = text.split(',')
    data = {}
    i = 0
    while i < len(parts):
        key = parts[i]
        if key == 'acc' or key == 'gyr':
            data[key] = [float(parts[i+1]), float(parts[i+2]), float(parts[i+3])]
            i += 4
        elif key in ['ges', 'aud', 'num']:
            data[key] = int(parts[i+1])
            i += 2
        elif key in ['pre', 'tem']:
            data[key] = float(parts[i+1])
            i += 2
        else:
            i += 1
    return data

# ---------- BLE Notification Handler ----------
def handle_notify(sender, data):
    try:
        text = data.decode("utf-8").strip()
        parsed_data = parse_sensor_data(text)
        json_data = json.dumps(parsed_data)
        mqtt_client.publish(TOPIC_SENSOR, json_data)
    except Exception as e:
        print(f"[BLE Error] {e}")

# ---------- MQTT on_message (control → BLE) ----------
def on_message(client, userdata, msg):
    global ble_client, loop
    try:
        payload = msg.payload.decode("utf-8").strip()
        # print(f"[MQTT→BLE] Received: {payload}")

        # Parse JSON
        data_dict = json.loads(payload)
        if "data" not in data_dict:
            print("[MQTT] Missing 'data' field.")
            return

        control_value = int(data_dict["data"])
        # print(f"[CONTROL] Sending value {control_value} to BLE")

        if ble_client and ble_client.is_connected:
            # Convert to 2 bytes (little endian)
            ble_bytes = control_value.to_bytes(2, byteorder='little', signed=True)
            # Schedule coroutine in BLE event loop thread
            asyncio.run_coroutine_threadsafe(
                ble_client.write_gatt_char(CONTROL_UUID, ble_bytes),
                loop
            )
            print(f"[BLE] Wrote {control_value} to {CONTROL_UUID}")
        else:
            print("[BLE] Not connected.")

    except json.JSONDecodeError:
        print("[MQTT] Invalid JSON.")
    except Exception as e:
        print(f"[Error] {e}")

# ---------- BLE Async Connection ----------
async def ble_main(device_name):
    global ble_client
    print(f"Scanning for {device_name}...")
    devices = await BleakScanner.discover()

    target = next((d for d in devices if d.name == device_name), None)
    if not target:
        print("Device not found.")
        return

    ble_client = BleakClient(target.address)
    async with ble_client:
        print(f"Connected to {target.name} ({target.address})")
        await ble_client.start_notify(SENSORS_UUID, handle_notify)
        print("Listening for BLE notifications...")

        while True:
            await asyncio.sleep(1)

# ---------- Main ----------
def main():
    global loop

    device_name = str(input("Edge device name: "))

    # Start BLE loop in separate thread
    loop = asyncio.new_event_loop()
    t = threading.Thread(target=lambda: loop.run_until_complete(ble_main(device_name)))
    t.start()

    # Setup MQTT
    mqtt_client.on_message = on_message
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.subscribe(TOPIC_CONTROL)
    mqtt_client.loop_forever()

if __name__ == "__main__":
    main()
