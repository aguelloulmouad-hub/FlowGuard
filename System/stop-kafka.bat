@echo off

echo Stopping Kafka and ZooKeeper...

for /f "tokens=5" %%a in ('netstat -ano ^| findstr :9092') do taskkill /PID %%a /F
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :2181') do taskkill /PID %%a /F

echo All services stopped.
pause