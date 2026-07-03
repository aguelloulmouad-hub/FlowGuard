@echo off
cd /d C:\kafka

echo Starting ZooKeeper...
start "ZooKeeper" cmd /k bin\windows\zookeeper-server-start.bat config\zookeeper.properties

timeout /t 5

echo Starting Kafka...
start "Kafka" cmd /k bin\windows\kafka-server-start.bat config\server.properties

echo Done. Kafka and ZooKeeper are starting...
pause