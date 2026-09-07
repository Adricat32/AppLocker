# App Locker

Aplicación de escritorio para cifrar archivos y carpetas localmente con una contraseña y una sesión de propietario.

## Requisitos

- Python 3.10 o superior
- Windows, macOS o Linux con Tkinter

## Ejecutar

```powershell
python -m pip install -r requirements.txt
python main.py
```

También puedes usar `AppLocker.exe` dentro de esta carpeta para abrir la aplicación con doble clic, sin consola.

Después de iniciar sesión, elige el modo **Cifrar** para bloquear archivos o carpetas, o **Ejecutar / ver contenido** para consultar un `.locked` sin restaurarlo.

También puedes arrastrar un archivo o una carpeta desde el Explorador de Windows hasta la zona de arrastre de la ventana. Se acepta una ruta por operación.

## Actualizaciones

Antes del inicio de sesión, la app consulta opcionalmente `updater.py`. Si existe una versión nueva, muestra sus datos y notas, ofrece **Saber más** y pregunta si se quiere actualizar. La actualización es voluntaria; elegir **Más tarde**, no tener conexión o tener un servidor caído permite iniciar sesión normalmente.

Para activar las actualizaciones, cambia `UPDATE_MANIFEST_URL` en `updater.py` por una URL HTTPS pública y publica allí un manifiesto basado en `update.example.json`. `installer_url` debe apuntar a un instalador de Windows y `sha256` debe contener su SHA-256 exacto. Se recomienda firmar digitalmente el instalador.
El instalador está definido en `installer.iss`. Para preparar una entrega, genera primero `AppLocker.exe` y ejecuta `make_release.ps1`; el script compila `AppLocker-Setup-<versión>.exe`, calcula su SHA-256 y crea `..\update.json` en la raíz del repositorio. Solo falta subir el instalador a una Release y el `update.json` a la raíz.

La separación del proyecto es intencional: `app.py` contiene la lógica de cifrado, cuentas, recuperación y auditoría; `interfaz.py` contiene la ventana; `main.py` es el lanzador.

## Uso

1. Elige un archivo o una carpeta completa.
2. Escribe una contraseña de al menos 8 caracteres y repítela al cifrar.
3. Pulsa **Cifrar y bloquear**. El original se elimina únicamente después de validar que el archivo cifrado se creó correctamente.
4. Para recuperar el archivo o carpeta, selecciona el contenedor `.locked`, escribe la contraseña y pulsa **Desbloquear**.
5. Si olvidaste la contraseña, inicia sesión con la opción de recuperación de Windows. App Locker usa DPAPI de Windows para comprobar la cuenta propietaria y recuperar los archivos sin guardar la contraseña.

El contenido se cifra con AES-256-GCM y cada contenedor tiene una clave aleatoria propia. Las carpetas se empaquetan conservando su estructura y después se cifran. La clave queda protegida tanto por la contraseña como por una clave de recuperación almacenada cifrada con DPAPI de Windows, ligada al perfil de usuario de Windows que creó la cuenta. Una contraseña incorrecta, otro usuario de Windows o un contenedor alterado hacen que la operación falle.

La configuración de la cuenta se guarda en `app_locker.json`. Los accesos y operaciones se registran en `app_locker_audit.json` con fecha UTC, usuario de App Locker, usuario de Windows, equipo, archivo, acción, método y resultado. Por seguridad, nunca se almacena la contraseña, ni siquiera cifrada: solo se verifica y se registra el método usado.

**Importante:** la recuperación solo funciona desde la cuenta de Windows propietaria que creó App Locker. Si pierdes la contraseña y también el acceso a esa cuenta o al equipo, no existe una forma de recuperar el archivo. La app no envía archivos ni contraseñas a internet.
