@echo off
REM Cambiamos a la carpeta del proyecto
cd /d "E:\DESCARGAS\FlyCloudOne_FULL_v2"

REM Activar el entorno virtual si tienes uno (descomenta si lo usas)
REM call venv\Scripts\activate

REM Ejecutar Flask
python app.py

pause
