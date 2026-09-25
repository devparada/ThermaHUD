import ctypes
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

# Consola en UTF-8 para los caracteres de los cuadros (║ ╔ ═ ...)
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    from colorama import init, Fore, Style

    init()
    COLORAMA = True
except ImportError:
    COLORAMA = False

VERSION = "0.0.3"
BOX_WIDTH = 44  # El ancho total de los cuadros

# Umbrales de temperatura y tiempos del HUD (evita numeros magicos)
TEMP_OK = 65  # < 65 °C verde
TEMP_HOT = 80  # < 80 °C amarillo; >= 80 rojo
POLL_SECS = 1.5
POST_INSTALL_GRACE = 2  # margen para que el servicio de PawnIO despierte

# Descarga oficial de PawnIO
PAWN_SETUP_URL = "https://github.com/namazso/PawnIO.Setup/releases/latest/download/PawnIO_setup.exe"
PAWN_RELEASES_URL = "https://github.com/namazso/PawnIO.Setup/releases/latest"

# Respuestas validas al prompt [S/n] (la cadena vacia es un Enter a secas)
ACCEPTED_WORDS = ("", "s", "si", "sí", "y", "yes")

# Por defecto el sistema queda limpio: se desinstala PawnIO al cerrar y se
# reinstala (siempre la ultima version) al arrancar. Con --keep-driver se
# deja instalado como cualquier driver de sistema (estilo HWiNFO persistente).
PORTABLE = "--keep-driver" not in sys.argv[1:]


def add_dll_directory(path):
    """Agrega una ruta al directorio de búsqueda de DLL en Windows (solo de Windows 7 para adelante)
    """
    if os.name == "nt":
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            AddDllDirectory = kernel32.AddDllDirectory
            AddDllDirectory.argtypes = [ctypes.c_wchar_p]
            AddDllDirectory.restype = ctypes.c_void_p
            # Un puntero devuelto distinto de NULL confirma que la ruta se registro.
            dll_dir_handle = AddDllDirectory(path)
            if not dll_dir_handle:
                raise ctypes.WinError(ctypes.get_last_error())
        except Exception as e:
            print(f"[WARNING] No se pudo añadir ruta con AddDllDirectory: {e}")


def get_dll_dir():
    """En el exe de PyInstaller las DLLs van a la subcarpeta libs"""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, "libs")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib")


# --- Cuadros en consola ---

def print_header():
    def print_line(content):
        print(f"║ {content.ljust(BOX_WIDTH - 4)} ║")

    print("╔" + "═" * (BOX_WIDTH - 2) + "╗")
    print_line(f"ThermaHUD v{VERSION}".center(BOX_WIDTH - 4))
    print("╚" + "═" * (BOX_WIDTH - 2) + "╝")


def print_temperature_box():
    print("╔" + "═" * (BOX_WIDTH - 2) + "╗")
    print("║" + " " * (BOX_WIDTH - 2) + "║")
    print("╚" + "═" * (BOX_WIDTH - 2) + "╝")


def get_temperature_color(temp):
    if temp < TEMP_OK:
        return Fore.GREEN
    elif temp < TEMP_HOT:
        return Fore.YELLOW
    else:
        return Fore.RED


def update_temperature(temp):
    inner_width = BOX_WIDTH - 4
    bright = Style.BRIGHT if COLORAMA else ""
    reset = Style.RESET_ALL if COLORAMA else ""

    if temp is None:
        color = ""
        temp_text = "CPU: N/A"
    else:
        color = get_temperature_color(temp) if COLORAMA else ""
        temp_text = f"CPU: {temp:.1f} °C"

    sys.stdout.write("\033[F\033[F")  # Subir 2 líneas
    sys.stdout.flush()

    line_content = f"{bright}{color}{temp_text:<{inner_width}}{reset}{bright}"

    print(f"║ {line_content} ║")
    print()  # Mantener la línea vacia


# --- PawnIO ---

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def relaunch_self():
    """Relanza el propio programa elevado con RunAs y termina el proceso
    actual. Devuelve False si no se pudo relanzar.
    """
    if hasattr(sys, "_MEIPASS"):  # exe compilado: relanza a sí mismo
        target = os.path.abspath(sys.argv[0])
        args = ""
    else:  # script: relanza python con este script
        target = sys.executable
        script = os.path.abspath(sys.argv[0]).replace('"', '`"')
        args = f" -ArgumentList '\"{script}\"'"

    cmd = f"Start-Process -FilePath '{target}'{args} -Verb RunAs"

    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", cmd],
        check=False,
    )
    return result.returncode == 0


def ensure_admin():
    """PawnIO solo permite acceder al dispositivo desde procesos elevados"""
    if is_admin():
        return

    print("ThermaHUD necesita permisos de administrador para leer el hardware.")
    answer = input("¿Relanzar como administrador? [S/n]: ").strip().lower()
    if answer not in ACCEPTED_WORDS:
        print(
            "\nCancelando.",
            "Vuelve a ejecutarlo desde una consola con permisos de administrador.",
        )
        sys.exit(0)

    if not relaunch_self():
        print("[ERROR] No se pudo relanzar el programa elevado.")
    sys.exit(0)


def run_pawn_installer(installer_path):
    """El instalador necesita privilegios de administrador.
    Devuelve el exit code del instalador (0 = ok).
    """
    if is_admin():
        proc = subprocess.run(
            [installer_path, "-install", "-silent"],
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return proc.returncode
    proc = subprocess.run(
        [
            "powershell", "-NoProfile", "-Command",
            f"$p = Start-Process -FilePath '{installer_path}' "
            f"-ArgumentList '-install','-silent' -Verb RunAs -Wait -PassThru; "
            f"exit $p.ExitCode",
        ],
        check=False,
    )
    return proc.returncode


def download_pawn_setup(dst):
    urllib.request.urlretrieve(PAWN_SETUP_URL, dst)


def ensure_pawnio():
    """Solo se puede llamar tras cargar la DLL de LibreHardwareMonitor"""
    try:
        from LibreHardwareMonitor.PawnIo import PawnIo  # type: ignore
    except Exception as e:
        print(f"[ERROR] No se pudo cargar el módulo PawnIO: {e}")
        return False

    try:
        installed = bool(PawnIo.IsInstalled)
    except Exception:
        installed = False
    if not installed:
        # El check in-process (PawnIo.IsInstalled) no se refresca tras una
        # instalacion recien hecha en este mismo proceso: el registro es la
        # señal fiable de que el driver ya está instalado.
        installed = pawnio_still_installed()

    if installed:
        return True

    # Instalación silenciosa: el único output en pantalla son los errores.
    dst = os.path.join(tempfile.gettempdir(), "PawnIO_setup.exe")
    try:
        download_pawn_setup(dst)
    except Exception as e:
        print(f"[ERROR] No se pudo descargar el instalador de PawnIO: {e}")
        print(
            "\nPuedes descargarlo manualmente desde:\n"
            f"  {PAWN_RELEASES_URL}\n"
            "Una vez instalado, vuelve a ejecutar ThermaHUD."
        )
        return False

    try:
        rc = run_pawn_installer(dst)
    except Exception as e:
        print(f"[ERROR] La instalación de PawnIO falló: {e}")
        return False
    if rc not in (0, None, 3010):
        # 3010 = "reinicio requerido" de Inno Setup: la instalación SÍ acabó
        print(f"[ERROR] El instalador de PawnIO terminó con código {rc}.")
        print("\nSi Windows mostró un aviso (SmartScreen/Defender),")
        print("pulsa 'Ejecutar de todas formas' / 'Sí' y reintenta.")

    if not pawnio_still_installed():
        print("\n[ERROR] PawnIO sigue sin estar disponible tras la instalación.")
        print(
            "Puedes descargarlo manualmente desde:\n"
            f"  {PAWN_RELEASES_URL}\n"
            "Una vez instalado, vuelve a ejecutar ThermaHUD."
        )
        return False

    time.sleep(POST_INSTALL_GRACE)
    return True


# --- Lectura de temperatura (sin IVisitor, carga directa de la DLL) ---

def get_cpu_temperature(computer, HardwareType, SensorType):
    values = []
    for hw in computer.Hardware:
        if not hw.HardwareType.Equals(HardwareType.Cpu):
            continue
        try:
            hw.Update()
        except Exception:
            continue
        for sensor in hw.Sensors:
            if not sensor.SensorType.Equals(SensorType.Temperature):
                continue
            name = sensor.Name or ""
            lowered = name.lower()
            if ("package" in lowered or "tctl" in lowered) and sensor.Value is not None:
                values.append(float(sensor.Value))
    if not values:
        return None
    return sum(values) / len(values)


UNINSTALL_KEY = "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall"


def _find_pawn_uninstall_entry():
    """Inno Setup registra la desinstalación como <AppId>_is1 (no como
    "PawnIO"), asi que no vale una ruta fija: enumeramos las subclaves de
    Uninstall en las vistas 64 y 32 bits y localizamos la que tenga el
    DisplayName de PawnIO. Devuelve su QuietUninstallString/UninstallString.
    """
    import winreg

    for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
        try:
            parent = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, UNINSTALL_KEY,
                0, winreg.KEY_READ | view,
            )
        except OSError:
            continue
        with parent:
            i = 0
            while True:
                try:
                    subkey = winreg.EnumKey(parent, i)
                except OSError:
                    break
                i += 1
                try:
                    with winreg.OpenKey(parent, subkey) as h:
                        name, _ = winreg.QueryValueEx(h, "DisplayName")
                        if "pawnio" not in (name or "").lower():
                            continue
                        for value in ("QuietUninstallString", "UninstallString"):
                            try:
                                val = winreg.QueryValueEx(h, value)[0]
                                if val:
                                    return val
                            except OSError:
                                continue
                except OSError:
                    continue
    return None


def pawnio_still_installed():
    """True si sigue habiendo una entrada de PawnIO en el registro"""
    return _find_pawn_uninstall_entry() is not None


def get_pawn_uninstaller():
    """Devuelve el QuietUninstallString/UninstallString del registro, si existe"""
    return _find_pawn_uninstall_entry()


def split_quoted(value):
    """Separa la ruta del exe y sus argumentos respetando las comillas"""
    value = value.strip()
    if value.startswith('"'):
        end = value.find('"', 1)
        if end < 0:
            return None, ""
        return value[1:end], value[end + 1:].strip()
    idx = value.find(" ")
    if idx < 0:
        return value, ""
    return value[:idx], value[idx + 1:].strip()


_close_ctrl_handler = None  # referencia global: sin ella el GC libera el callback
_pawn_uninstalled = False  # para no intentar desinstalar dos veces (Ctrl+C + X)

# Coordinación entre el bucle del HUD y el handler de cierre de consola:
# al cerrar la ventana, primero paramos el bucle (giro limpio) y después
# desinstalamos, para que la temperatura no siga imprimiéndose.
stop_event = threading.Event()


def install_close_handler():
    """Cerrar la ventana de consola con la X mata el proceso sin pasar por
    finally/KeyboardInterrupt. SetConsoleCtrlHandler da unos segundos de
    margen en CTRL_CLOSE_EVENT: los usamos para parar el bucle del HUD
    (que por otra parte intercalaría temperaturas con la desinstalación)
    y desinstalar PawnIO en silencio después.
    """
    global _close_ctrl_handler
    if os.name != "nt" or _close_ctrl_handler is not None:
        return

    @ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_uint)
    def handler(ctrl_type):
        # 2 = CTRL_CLOSE_EVENT, 5 = CTRL_LOGOFF_EVENT, 6 = CTRL_SHUTDOWN_EVENT
        if ctrl_type in (2, 5, 6):
            try:
                # 1) Parar el bucle del HUD inmediatamente
                stop_event.set()
                # 2) Desinstalador detachado YA: el margen de gracia de Windows
                #    es corto (~5 s) y el proceso puede morir antes de que acabe.
                quiet = get_pawn_uninstaller()
                exe, rest = split_quoted(quiet or "")
                if exe:
                    if not rest:
                        rest = "-uninstall,-silent"
                    args = rest.replace(" ", ",").split(",")
                    subprocess.Popen(
                        [exe] + args,
                        creationflags=0x00000008 | 0x00000200,  # DETACHED_PROCESS | NEW_PROCESS_GROUP
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        close_fds=True,
                    )
            except Exception:
                pass
            finally:
                # Marcador de limpieza pendiente: si el desinstalador
                # detachado tampoco llega a ejecutarse (proceso muerto
                # antes de arrancarlo), la siguiente sesion portable
                # completara la limpieza al arrancar.
                try:
                    open(cleanup_marker(), "w").close()
                except Exception:
                    pass
        return 0  # 0 = continuar con el cierre por defecto

    _close_ctrl_handler = handler
    ctypes.windll.kernel32.SetConsoleCtrlHandler(handler, 1)


def cleanup_marker():
    """Marca de "desinstalacion pendiente" de una sesion que se cerro de golpe"""
    return os.path.join(tempfile.gettempdir(), "thermahud_cleanup.pending")


def collect_deferred_cleanup():
    """Si una sesion anterior murio con desinstalacion pendiente (ventana
    cerrada con la X y el desinstalador no llego a acabar), completamos la
    limpieza al arrancar: proceso ya elevado, sin UAC extra.
    """
    marker = cleanup_marker()
    if not os.path.exists(marker):
        return
    try:
        os.remove(marker)
    except Exception:
        pass
    if pawnio_still_installed():
        # desinstalacion silenciosa: solo se avisa si algo falla
        uninstall_pawn_io()


def uninstall_pawn_io():
    global _pawn_uninstalled
    if _pawn_uninstalled:
        return
    _pawn_uninstalled = True
    # Solo en modo portable: al cerrar, desinstala PawnIO para no dejar
    # rastro en el sistema.
    quiet = get_pawn_uninstaller()
    if not quiet:
        print("[WARNING] No se encontro el desinstalador de PawnIO.")
        return
    exe, rest = split_quoted(quiet)
    if not exe:
        print("[WARNING] No se pudo parsear el desinstalador de PawnIO.")
        return
    if not rest:
        rest = "-uninstall,-silent"
    else:
        rest = rest.replace(" ", ",")
    args = rest.split(",")
    try:
        if is_admin():
            # Proceso ya elevado: con el unico UAC del arranque basta,
            # no hace falta un segundo RunAs
            subprocess.run([exe] + args, check=False, creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            subprocess.run(
                [
                    "powershell", "-NoProfile", "-Command",
                    "Start-Process -FilePath '" + exe + "' "
                                                        "-ArgumentList '" + rest + "' -Verb RunAs -Wait -PassThru",
                ],
                check=False,
            )
    except Exception as e:
        print("[WARNING] No se pudo desinstalar PawnIO:", e)

    # Verificación: la entrada de desinstalacion debe desaparecer del registro
    time.sleep(1)
    if pawnio_still_installed():
        print("[WARNING] PawnIO sigue instalado.")
        print(
            "Desinstalalo a mano desde Configuración > Aplicaciones, o "
            "ejecutando el desinstalador de PawnIO con '-uninstall -silent'."
        )
    # silencio si sale bien: sin mensajes, la consola simplemente muere limpia


# Referencia global al resolver de ensamblados .NET: sin ella el GC libera el
# callback y pythonnet deja de servir las DLLs dependientes de LHM.
_assembly_resolver = None


def install_assembly_resolver(dll_dir):
    """En el exe de PyInstaller las DLLs de .NET viven en _MEIPASS/libs, una
    subcarpeta que el fusion de .NET Framework no sondea. Un handler de
    AssemblyResolve las sirve por nombre (ignorando la version pedida, p.ej.
    System.Memory 4.0.5.0 <-> 4.0.2.0), igual que hace pythonnet en consola.
    """
    global _assembly_resolver
    try:
        from System import AppDomain, ResolveEventHandler
        from System.Reflection import Assembly

        def on_resolve(sender, e):
            name = e.Name.split(",")[0]
            path = os.path.join(dll_dir, name + ".dll")
            if os.path.exists(path):
                try:
                    return Assembly.LoadFile(path)
                except Exception:
                    pass
            return None

        _assembly_resolver = ResolveEventHandler(on_resolve)
        AppDomain.CurrentDomain.add_AssemblyResolve(_assembly_resolver)
    except Exception as e:
        print(f"[WARNING] No se pudo instalar el resolver de ensamblados: {e}")


def prepare_dlls():
    """Deja el proceso listo para cargar LibreHardwareMonitorLib.

    Comprueba elevación, hace la limpieza diferida de una sesión anterior
    que se cerró de golpe, localiza las DLLs y las hace visibles para
    Windows. Si algo falla, el propio proceso termina aquí.
    """
    ensure_admin()

    if PORTABLE:
        collect_deferred_cleanup()

    dll_dir = os.path.abspath(get_dll_dir())
    lhm_path = os.path.join(dll_dir, "LibreHardwareMonitorLib.dll")
    if not os.path.exists(lhm_path):
        print(f"[ERROR] No se encontró {lhm_path}")
        sys.exit(1)

    # Añade la carpeta al PATH para que Windows encuentre las DLLs dependientes
    os.environ["PATH"] = dll_dir + os.pathsep + os.environ.get("PATH", "")

    add_dll_directory(dll_dir)

    import clr
    try:
        clr.AddReference(lhm_path)
    except Exception as e:
        print(f"[ERROR] No se pudo añadir la referencia con clr: {e}")
        sys.exit(1)

    install_assembly_resolver(dll_dir)


def open_computer():
    """Importa las clases de LHM y crea el objeto Computer listo para leer."""
    try:
        from LibreHardwareMonitor.Hardware import (
            Computer,
            HardwareType,
            SensorType,
        )  # type: ignore
    except Exception as e:
        print(f"[ERROR] No se pudo importar LibreHardwareMonitor: {e}")
        sys.exit(1)

    # Cerrar por la X de la consola también debe desinstalar PawnIO
    if PORTABLE:
        install_close_handler()

    computer = Computer()
    computer.IsCpuEnabled = True
    return computer, HardwareType, SensorType


def run_hud(computer, HardwareType, SensorType):
    """Bucle principal del HUD: actualiza la temperatura hasta el cierre.

    stop_event lo activa el handler de cierre de consola (X de la ventana):
    la lectura de temperatura cesa antes de desinstalar.
    """
    computer.Open()

    print_header()
    print_temperature_box()

    try:
        while not stop_event.is_set():
            temp = get_cpu_temperature(computer, HardwareType, SensorType)
            update_temperature(temp)
            if stop_event.wait(POLL_SECS):
                break

    except KeyboardInterrupt:
        stop_event.set()  # Ctrl+C también activa la parada ordenada
        print("\nLectura finalizada por el usuario")
    except Exception as e:
        stop_event.set()
        print(f"\n[ERROR] Lectura de temperatura interrumpida: {e}")
    finally:
        try:
            computer.Close()
        except Exception:
            pass


def main():
    """Punto de entrada: prepara DLLs, asegura PawnIO y ejecuta el HUD."""
    prepare_dlls()

    if not ensure_pawnio():
        print("\nCancelando: PawnIO es necesario para leer la temperatura del CPU.")
        sys.exit(0)

    computer, HardwareType, SensorType = open_computer()
    run_hud(computer, HardwareType, SensorType)

    if PORTABLE:
        uninstall_pawn_io()


if __name__ == "__main__":
    main()
