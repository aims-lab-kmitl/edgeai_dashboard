@echo off
echo ======================================
echo  BLE to MQTT + Docker Restart Script
echo ======================================

echo.
echo [1/3] Stopping Docker Compose...
docker compose down

echo.
echo [2/3] Starting Docker Compose...
docker compose up -d

echo.
echo [3/3] Running BLE to MQTT Python script...
python ble_to_mqtt.py

echo.
echo ======================================
echo    All tasks completed successfully
echo ======================================
pause
