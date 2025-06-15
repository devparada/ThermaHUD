import clr
import ctypes
import os
import sys
import time

try:
    from colorama import init, Fore, Style
    init()
    COLORAMA = True
except ImportError:
    COLORAMA = False

VERSION = "0.0.2"
BOX_WIDTH = 44  # El ancho total de los cuadros

def add_dll_directory(path):
    # Agrega una ruta al directorio de búsqueda de DLL en Windows (solo de Windows 7 para adelante)
    if os.name == "nt":
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            AddDllDirectory = kernel32.AddDllDirectory
            AddDllDirectory.argtypes = [ctypes.c_wchar_p]
            AddDllDirectory.restype = ctypes.c_void_p
            handle = AddDllDirectory(path)
            if not handle:
                raise ctypes.WinError(ctypes.get_last_error())
        except Exception as e:
            print(f"[WARNING] No se pudo añadir ruta con AddDllDirectory: {e}")

def print_cpu_sensors_simple(reader):
    def print_line(content=""):
        print(f"║ {content.ljust(BOX_WIDTH - 4)} ║")

    def print_box_top(): print("╔" + "═" * (BOX_WIDTH - 2) + "╗")
    def print_box_bottom(): print("╚" + "═" * (BOX_WIDTH - 2) + "╝")

    print_box_top()
    print_line(f"ThermaHUD v{VERSION}".center(BOX_WIDTH - 4))
    print_box_bottom()

    for hw in reader.GetCpuSensors():
        print_box_top()
        print_line(f"Hardware: {hw.Name}")
        for sensor in hw.Sensors:
            print_line(f"  └─ Sensor: {sensor.Name}")
        for sub in hw.SubHardwares:
            print_line(f"SubHardware: {sub.Name}")
            for sensor in sub.Sensors:
                print_line(f"  └─ Sensor: {sensor.Name}")
        print_box_bottom()

def get_temperature_color(temp):
    if temp < 65:
        return Fore.GREEN
    elif temp < 80:
        return Fore.YELLOW
    else:
        return Fore.RED

def print_temperature_box():
    print("╔" + "═" * (BOX_WIDTH - 2) + "╗")
    print("║" + " " * (BOX_WIDTH - 2) + "║")
    print("╚" + "═" * (BOX_WIDTH - 2) + "╝")

def update_temperature(temp):
    inner_width = BOX_WIDTH - 4
    bright = Style.BRIGHT if COLORAMA else ""
    reset = Style.RESET_ALL if COLORAMA else ""
    color = get_temperature_color(temp) if COLORAMA else ""

    sys.stdout.write("\033[F\033[F")  # Subir 2 líneas
    sys.stdout.flush()

    temp_text = f"CPU: {temp:.1f} °C"
    line_content = f"{bright}{color}{temp_text:<{inner_width}}{reset}{bright}"

    print(f"║ {line_content} ║")
    print()  # Mantener la línea vacia

def main():
    # Rutas DLLs
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
        therma_path = os.path.join(base_path, "libs", "ThermaHUDLib.dll")
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
        therma_path = os.path.join(base_path, "..", "target", "ThermaHUDLib.dll")

    # Añade la carpeta temporal al PATH para que Windows encuentre las DLLs dependientes
    os.environ["PATH"] = base_path + os.environ.get("PATH", "")

    add_dll_directory(base_path)

    try:
        clr.AddReference(therma_path)
    except Exception as e:
        print(f"[ERROR] No se pudo añadir la referencia con clr: {e}")
        sys.exit(1)

    try:
        from ThermaHUDLib import ThermaHUD # type: ignore
    except Exception as e:
        print(f"[ERROR] No se pudo importar ThermaHUD: {e}")
        sys.exit(1)

    reader = ThermaHUD()

    try:
        print_cpu_sensors_simple(reader)
        print_temperature_box()

        while True:
            temp = reader.GetCpuTemperature()
            update_temperature(temp if temp is not None else 0)
            time.sleep(1.5)

    except KeyboardInterrupt:
        print("\nLectura finalizada por el usuario")
    finally:
        reader.Dispose()

if __name__ == "__main__":
    main()
