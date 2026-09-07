$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

pyinstaller --noconfirm --clean --windowed --onefile --name AppLocker --paths Cifrado --distpath Cifrado --workpath Cifrado\build --specpath Cifrado Cifrado\main.py

Write-Host "Ejecutable creado en Cifrado\AppLocker.exe"
