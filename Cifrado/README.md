# App Locker 1.3.0

Aplicación de escritorio para cifrar archivos y carpetas localmente con una contraseña.

## Requisitos

- Python 3.10 o superior
- Windows con Tkinter

## Ejecutar

```powershell
python -m pip install -r requirements.txt
python main.py
```

También puedes usar `AppLocker.exe` dentro de esta carpeta para abrir la aplicación con doble clic.

Después de iniciar sesión, elige el modo **Cifrar** para bloquear archivos o carpetas, **Ejecutar / ver contenido** para consultar un `.locked` sin restaurarlo, o **Descifrar y recuperar** para restaurarlo.

La versión 1.3.0 permite elegir Español, English o Français. Para cada contenedor nuevo App Locker elige automáticamente un método mediante el generador seguro del sistema. El identificador queda guardado y autenticado dentro del propio archivo `.locked`, por lo que el método correcto se selecciona automáticamente al inspeccionar o descifrar.

También puedes arrastrar un archivo o una carpeta desde el Explorador de Windows hasta la zona de arrastre de la ventana.

## Actualizaciones

Antes del inicio de sesión, la app consulta opcionalmente `updater.py`. Si existe una versión nueva, muestra sus datos y notas, ofrece **Saber más** y pregunta si se quiere actualizar. La actualización es voluntaria; elegir **Más tarde**, no tener conexión o tener un servidor caído permite iniciar sesión normalmente.

Para activar las actualizaciones, cambia `UPDATE_MANIFEST_URL` en `updater.py` por una URL HTTPS pública y publica allí un manifiesto basado en `update.example.json`. `installer_url` debe apuntar a un instalador de Windows y `sha256` debe contener su SHA-256 exacto. Se recomienda firmar digitalmente el instalador.
El instalador está definido en `installer.iss`. Para preparar una entrega, genera primero `AppLocker.exe` y ejecuta `make_release.ps1`; el script compila `AppLocker-Setup-<versión>.exe`, calcula su SHA-256 y crea `..\update.json` en la raíz del repositorio. Solo falta subir el instalador a una Release y el `update.json` a la raíz.

La separación del proyecto es intencional: `app.py` contiene la lógica de cifrado, cuentas, recuperación y auditoría; `translations.py` contiene los tres idiomas; `interfaz.py` contiene la ventana; `main.py` es el lanzador.

## Uso

1. Elige un archivo o una carpeta completa.
2. Escribe una contraseña de al menos 8 caracteres y repítela al cifrar.
3. Pulsa **Cifrar y bloquear**. El original se elimina únicamente después de validar que el archivo cifrado se creó correctamente.
4. Para recuperar el archivo o carpeta, selecciona el contenedor `.locked`, escribe la contraseña y pulsa **Desbloquear**.
5. Si olvidaste la contraseña, inicia sesión con la opción de recuperación de Windows. App Locker usa DPAPI de Windows para comprobar la cuenta propietaria y recuperar los archivos sin guardar la contraseña.

Cada contenedor tiene una clave aleatoria propia. Las carpetas se empaquetan conservando su estructura y después se protegen. La clave queda protegida tanto por la contraseña como por una clave de recuperación almacenada de forma segura con DPAPI de Windows, ligada al perfil de usuario de Windows que creó la cuenta. Una contraseña incorrecta, otro usuario de Windows o un contenedor alterado hacen que la operación falle.

La configuración de la cuenta se guarda en `app_locker.json`. Los accesos y operaciones se registran en `app_locker_audit.json` con fecha UTC, usuario de App Locker, usuario de Windows, equipo, archivo, acción, método y resultado. Por seguridad, nunca se almacena la contraseña, ni siquiera cifrada: solo se verifica y se registra el método usado.

**Importante:** la recuperación solo funciona desde la cuenta de Windows propietaria que creó App Locker. Si pierdes la contraseña y también el acceso a esa cuenta o al equipo, no existe una forma de recuperar el archivo. La app no envía archivos ni contraseñas a internet.
