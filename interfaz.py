import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from tkinterdnd2 import DND_FILES, TkinterDnD

import app
import updater


class AppLockerWindow(TkinterDnD.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("App Locker")
        self.geometry("720x620")
        self.minsize(620, 500)
        self.configure(bg="#f4f1eb")
        self.selected_path: Path | None = None
        self.session: app.Session | None = None
        self.busy = False
        self.withdraw()
        if self._offer_update():
            self.destroy()
            return
        if not self._authenticate():
            self.destroy()
            return
        self._build_ui()
        self.deiconify()

    def _offer_update(self) -> bool:
        update = updater.get_available_update()
        if not update:
            return False
        choice = updater.show_update_dialog(self, update)
        if choice != "update":
            return False
        try:
            updater.download_and_launch_installer(update)
            return True
        except (OSError, RuntimeError, ValueError) as error:
            messagebox.showerror("No se pudo actualizar", str(error), parent=self)
            return False

    def _authenticate(self) -> bool:
        if not app.CONFIG_PATH.exists():
            username = simpledialog.askstring("Crear cuenta", "Elige el usuario propietario:", parent=self)
            password = simpledialog.askstring("Crear cuenta", "Crea la contraseña de acceso:", show="*", parent=self)
            confirm = simpledialog.askstring("Crear cuenta", "Repite la contraseña:", show="*", parent=self)
            if not username or not password or password != confirm:
                messagebox.showerror("Cuenta no creada", "Necesitas un usuario y dos contraseñas iguales.")
                return False
            try:
                self.session = app.create_account(username, password)
            except (OSError, RuntimeError, ValueError) as error:
                messagebox.showerror("No se pudo crear la cuenta", str(error))
                return False
            messagebox.showinfo("Cuenta creada", "La recuperación queda ligada a tu cuenta de Windows.")
            return True

        username = simpledialog.askstring("Iniciar sesión", "Usuario:", parent=self)
        password = simpledialog.askstring("Iniciar sesión", "Contraseña:", show="*", parent=self)
        try:
            self.session = app.login(username or "", password or "")
            return True
        except (OSError, RuntimeError, ValueError) as error:
            app.audit(username or "desconocido", "login", None, False, "password", str(error))
            if messagebox.askyesno("Acceso rechazado", "¿Usar la recuperación protegida por tu cuenta de Windows?", parent=self):
                try:
                    self.session = app.login_with_windows_recovery()
                    return True
                except (OSError, RuntimeError, ValueError) as recovery_error:
                    messagebox.showerror("Recuperación rechazada", str(recovery_error))
            else:
                messagebox.showerror("Acceso rechazado", str(error))
            return False

    def _build_ui(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#f4f1eb")
        style.configure("TLabel", background="#f4f1eb", foreground="#24211d", font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 23), foreground="#172b26")
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10), foreground="#5f665f")
        style.configure("Action.TButton", font=("Segoe UI Semibold", 10), padding=(14, 9))
        style.configure("TEntry", padding=8)

        outer = ttk.Frame(self, padding=30)
        outer.pack(fill="both", expand=True)
        outer.drop_target_register(DND_FILES)
        outer.dnd_bind("<<Drop>>", self._drop_path)
        ttk.Label(outer, text="App Locker", style="Title.TLabel").pack(anchor="w")
        ttk.Label(outer, text=f"Sesión: {self.session.username} | AES-256-GCM", style="Subtitle.TLabel").pack(anchor="w", pady=(4, 14))

        mode_frame = ttk.Frame(outer)
        mode_frame.pack(fill="x", pady=(0, 14))
        ttk.Label(mode_frame, text="Modo:").pack(side="left")
        self.mode = tk.StringVar(value="encrypt")
        ttk.Radiobutton(mode_frame, text="Cifrar", variable=self.mode, value="encrypt", command=self._set_mode).pack(side="left", padx=(12, 8))
        ttk.Radiobutton(mode_frame, text="Ejecutar / ver contenido", variable=self.mode, value="inspect", command=self._set_mode).pack(side="left")

        file_row = ttk.Frame(outer)
        file_row.pack(fill="x")
        self.file_label = ttk.Label(file_row, text="Ningún archivo o carpeta seleccionada", anchor="w")
        self.file_label.pack(side="left", fill="x", expand=True)
        ttk.Button(file_row, text="Elegir archivo", command=self.choose_file).pack(side="right", padx=(6, 0))
        ttk.Button(file_row, text="Elegir carpeta", command=self.choose_folder).pack(side="right")

        self.drop_zone = tk.Label(
            outer,
            text="Arrastra aquí un archivo o una carpeta",
            height=2,
            bg="#e6eee8",
            fg="#1f4a3d",
            relief="groove",
            bd=1,
            font=("Segoe UI Semibold", 10),
        )
        self.drop_zone.pack(fill="x", pady=(12, 0))
        self.drop_zone.drop_target_register(DND_FILES)
        self.drop_zone.dnd_bind("<<Drop>>", self._drop_path)

        password_frame = ttk.Frame(outer)
        password_frame.pack(fill="x", pady=(22, 0))
        self.password_label = ttk.Label(password_frame, text="Contraseña del contenedor (mínimo 8 caracteres)")
        self.password_label.pack(anchor="w")
        self.password_entry = ttk.Entry(password_frame, show="*")
        self.password_entry.pack(fill="x", pady=(6, 12))
        self.confirm_label = ttk.Label(password_frame, text="Repite la contraseña al cifrar")
        self.confirm_label.pack(anchor="w")
        self.confirm_entry = ttk.Entry(password_frame, show="*")
        self.confirm_entry.pack(fill="x", pady=(6, 0))

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", pady=(24, 0))
        self.encrypt_button = ttk.Button(buttons, text="Cifrar y bloquear", style="Action.TButton", command=self.encrypt)
        self.encrypt_button.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.inspect_button = ttk.Button(buttons, text="Ver contenido", style="Action.TButton", command=self.inspect)
        self.inspect_button.pack(side="left", fill="x", expand=True, padx=(6, 0))

        listing_frame = ttk.Frame(outer)
        listing_frame.pack(fill="both", expand=True, pady=(18, 0))
        columns = ("name", "type", "size")
        self.contents = ttk.Treeview(listing_frame, columns=columns, show="headings", height=8)
        self.contents.heading("name", text="Nombre")
        self.contents.heading("type", text="Tipo")
        self.contents.heading("size", text="Tamaño")
        self.contents.column("name", width=460, anchor="w")
        self.contents.column("type", width=100, anchor="w")
        self.contents.column("size", width=110, anchor="e")
        scrollbar = ttk.Scrollbar(listing_frame, orient="vertical", command=self.contents.yview)
        self.contents.configure(yscrollcommand=scrollbar.set)
        self.contents.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        initial_status = "Modo recuperación de Windows activo." if self.session.recovery_mode else "Selecciona un archivo o carpeta."
        self.status = ttk.Label(outer, text=initial_status, style="Subtitle.TLabel", wraplength=540)
        self.status.pack(anchor="w", pady=(22, 0))
        self._set_mode()

    def _set_mode(self) -> None:
        inspecting = self.mode.get() == "inspect"
        self.confirm_entry.configure(state="disabled" if inspecting else "normal")
        self.confirm_label.configure(state="disabled" if inspecting else "normal")
        self.encrypt_button.configure(state="disabled" if inspecting else "normal")
        self.inspect_button.configure(state="normal" if inspecting else "disabled")
        self.password_label.configure(text="Contraseña del contenedor" if inspecting else "Contraseña del contenedor (mínimo 8 caracteres)")
        self.status.configure(text="Selecciona un contenedor .locked para verlo." if inspecting else "Selecciona un archivo o carpeta para cifrar.")

    def choose_file(self) -> None:
        path = filedialog.askopenfilename(title="Selecciona un archivo")
        if path:
            self._select(Path(path))

    def choose_folder(self) -> None:
        path = filedialog.askdirectory(title="Selecciona una carpeta")
        if path:
            self._select(Path(path))

    def _drop_path(self, event) -> None:
        paths = self.tk.splitlist(event.data)
        if len(paths) != 1:
            messagebox.showwarning("Una ruta cada vez", "Arrastra un solo archivo o una sola carpeta.")
            return
        path = Path(paths[0])
        if not path.exists():
            messagebox.showwarning("Ruta no válida", "La ruta arrastrada ya no existe.")
            return
        if self.mode.get() == "inspect" and (not path.is_file() or not path.name.endswith(app.LOCKED_SUFFIX)):
            messagebox.showwarning("Contenedor no válido", "En modo ejecutar debes arrastrar un archivo .locked.")
            return
        self._select(path)

    def _select(self, path: Path) -> None:
        self.selected_path = path
        self.file_label.configure(text=str(path))
        self.status.configure(text="Listo. Elige cifrar o desbloquear.")

    def _set_busy(self, value: bool) -> None:
        self.busy = value
        if value:
            self.encrypt_button.configure(state="disabled")
            self.inspect_button.configure(state="disabled")
        else:
            self._set_mode()

    def _run(self, action, success_text: str) -> None:
        if self.busy:
            return
        self._set_busy(True)
        self.status.configure(text="Procesando... no cierres la aplicación.")

        def worker() -> None:
            try:
                result = action()
                self.after(0, lambda: self._finished(success_text.format(result=result)))
            except Exception as error:
                self.after(0, lambda: self._failed(str(error)))

        threading.Thread(target=worker, daemon=True).start()

    def _finished(self, message: str) -> None:
        self._set_busy(False)
        self.status.configure(text=message)
        messagebox.showinfo("App Locker", message)

    def _failed(self, message: str) -> None:
        self._set_busy(False)
        self.status.configure(text="No se pudo completar la operación.")
        messagebox.showerror("App Locker", message)

    def _password(self, confirmation: bool) -> str:
        password = self.password_entry.get()
        if len(password) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres.")
        if confirmation and password != self.confirm_entry.get():
            raise ValueError("Las contraseñas no coinciden.")
        return password

    def encrypt(self) -> None:
        if not self.selected_path:
            messagebox.showwarning("Falta una ruta", "Selecciona un archivo o una carpeta.")
            return
        if self.selected_path.name.endswith(app.LOCKED_SUFFIX):
            messagebox.showwarning("Ya está bloqueado", "Esa ruta ya tiene formato App Locker.")
            return
        try:
            password = self._password(True)
        except ValueError as error:
            messagebox.showwarning("Contraseña no válida", str(error))
            return
        source = self.selected_path
        self._run(lambda: self._encrypt_and_remove(source, password), "Contenedor creado: {result}")

    def _encrypt_and_remove(self, source: Path, password: str) -> Path:
        try:
            destination = app.encrypt_path(source, password, self.session.recovery_key)
            app.remove_original(source)
            app.audit(self.session.username, "encrypt", source, True, "password")
            return destination
        except Exception as error:
            app.audit(self.session.username, "encrypt", source, False, "password", str(error))
            raise

    def inspect(self) -> None:
        if not self.selected_path or not self.selected_path.is_file():
            messagebox.showwarning("Falta un contenedor", "En modo ejecutar debes seleccionar un archivo .locked.")
            return
        if not self.selected_path.name.endswith(app.LOCKED_SUFFIX):
            messagebox.showwarning("Formato no válido", "Selecciona un archivo terminado en .locked.")
            return
        if self.session.recovery_mode:
            password = None
            method = "Windows DPAPI"
        else:
            password = self.password_entry.get()
            if len(password) < 8:
                messagebox.showwarning("Contraseña no válida", "Escribe la contraseña del contenedor.")
                return
            method = "password"
        source = self.selected_path
        self._run(lambda: self._inspect(source, password, method), "Contenido consultado: {result} elemento(s)")

    def _inspect(self, source: Path, password: str | None, method: str) -> int:
        try:
            entries = app.inspect_path(source, password, self.session.recovery_key)
            app.audit(self.session.username, "inspect", source, True, method)
            self.after(0, lambda: self._show_entries(entries))
            return len(entries)
        except Exception as error:
            app.audit(self.session.username, "inspect", source, False, method, str(error))
            raise

    def _show_entries(self, entries: list[dict]) -> None:
        for item in self.contents.get_children():
            self.contents.delete(item)
        for entry in entries:
            size = "-" if entry["type"] == "Carpeta" else f"{entry['size_bytes']:,} bytes"
            self.contents.insert("", "end", values=(entry["name"], entry["type"], size))

    def decrypt(self) -> None:
        if not self.selected_path or not self.selected_path.is_file():
            messagebox.showwarning("Falta un contenedor", "Selecciona un archivo .locked.")
            return
        if not self.selected_path.name.endswith(app.LOCKED_SUFFIX):
            messagebox.showwarning("Formato no válido", "Selecciona un archivo terminado en .locked.")
            return
        if self.session.recovery_mode:
            password = None
            method = "Windows DPAPI"
        else:
            try:
                password = self._password(False)
            except ValueError as error:
                messagebox.showwarning("Contraseña no válida", str(error))
                return
            method = "password"
        source = self.selected_path
        self._run(lambda: self._decrypt_and_remove(source, password, method), "Restaurado: {result}")

    def _decrypt_and_remove(self, source: Path, password: str | None, method: str) -> Path:
        try:
            destination = app.decrypt_path(source, password, self.session.recovery_key)
            app.remove_original(source)
            app.audit(self.session.username, "decrypt", source, True, method)
            return destination
        except Exception as error:
            app.audit(self.session.username, "decrypt", source, False, method, str(error))
            raise
