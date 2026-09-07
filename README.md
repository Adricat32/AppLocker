# App Locker

Aplicacion de escritorio para cifrar archivos y carpetas en Windows.

## Ejecutar desde codigo

```powershell
python -m pip install -r Cifrado\requirements.txt
python Cifrado\main.py
```

La aplicacion permite cifrar archivos y carpetas, consultar el contenido de contenedores `.locked`, usar arrastrar y soltar y comprobar actualizaciones antes del inicio de sesion.

El ejecutable y el instalador se generan con `Cifrado\make_release.ps1`. El archivo `update.json` en la raíz es el manifiesto público de actualizaciones.
