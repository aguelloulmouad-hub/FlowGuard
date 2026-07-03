@echo off
title FlowGuard Kafka Topic Creator

REM =========================================================
REM FlowGuard - Kafka Topics Setup
REM =========================================================

set KAFKA_HOME=C:\kafka

echo.
echo ========================================================
echo FlowGuard - Creation des topics Kafka
echo ========================================================
echo.

REM Vérification Kafka
if not exist "%KAFKA_HOME%\bin\windows\kafka-topics.bat" (
    echo [ERREUR] Kafka introuvable dans :
    echo %KAFKA_HOME%
    echo.
    pause
    exit /b 1
)

REM Aller dans le dossier Kafka
cd /d "%KAFKA_HOME%\bin\windows"

echo [1/5] Creation du topic transactions.raw
call kafka-topics.bat --create --if-not-exists --topic transactions.raw --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1

echo.
echo [2/5] Creation du topic predictions
call kafka-topics.bat --create --if-not-exists --topic predictions --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1

echo.
echo [3/5] Creation du topic alerts
call kafka-topics.bat --create --if-not-exists --topic alerts --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1

echo.
echo [4/5] Creation du topic model.updates
call kafka-topics.bat --create --if-not-exists --topic model.updates --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1

echo.
echo [5/5] Creation du topic federated.updates
call kafka-topics.bat --create --if-not-exists --topic federated.updates --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1

echo.
echo ========================================================
echo Liste des topics Kafka
echo ========================================================
echo.

call kafka-topics.bat --list --bootstrap-server localhost:9092

echo.
echo ========================================================
echo Setup termine
echo ========================================================
echo.
echo Appuyez sur une touche pour quitter...
pause >nul