@echo off
rem Arranca el panel sin dejar una consola abierta. Los errores van a porofesor.log.
cd /d "%~dp0"
start "" pyw -X utf8 -m porofesor
