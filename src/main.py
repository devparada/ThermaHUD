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
    sensors_list = reader.GetCpuSensors()
    for hw in sensors_list:
        print(f"Hardware: {hw.Name}")
        for sensor in hw.Sensors:
            print(f"  Sensor: {sensor.Name}")
        for sub in hw.SubHardwares:
            print(f"  SubHardware: {sub.Name}")
            for sensor in sub.Sensors:
                print(f"    Sensor: {sensor.Name}")
        print()  # línea vacía


def get_temperature_color(temp):
    if temp < 65:
        return Fore.GREEN
    elif temp < 80:
        return Fore.YELLOW
    else:
        return Fore.RED

def print_temperature(reader):
    try:
        temp = reader.GetCpuTemperature()
        if temp is None:
            print("No se pudo leer la temperatura")
            return

        temp_text = f"{temp:.1f} °C"
        color = get_temperature_color(temp) if COLORAMA else ""
        bright = Style.BRIGHT if COLORAMA else ""
        reset = Style.RESET_ALL if COLORAMA else ""

        line = f"\r{bright}CPU:{reset} {color}{temp_text}{reset}"
        sys.stdout.write(line)
        sys.stdout.flush()
    except Exception as e:
        print(f"\n[ERROR] Fallo al leer temperatura: {e}")

    time.sleep(1.5)

def main():
    # Rutas DLLs
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
        therma_path = os.path.join(base_path, "libs", "ThermaHUDLib.dll")
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
        therma_path = os.path.join(base_path, ".." , "target", "ThermaHUDLib.dll")

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
        print("=== INFO: Sensores disponibles ===")
        print_cpu_sensors_simple(reader)

        while True:
            print_temperature(reader)
    except KeyboardInterrupt:
        print("\nLectura finalizada por el usuario")
    finally:
        reader.Dispose()

if __name__ == "__main__":
    main()
