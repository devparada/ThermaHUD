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
        print("=== MODO DEBUG: Sensores disponibles ===")
        print_cpu_sensors_simple(reader)

        while True:
            temp = reader.GetCpuTemperature()

            if temp is not None:
                temp_text = f"{temp:.1f} C"

                if temp is not None and temp < 60:
                    color = Fore.GREEN
                elif temp is not None and temp < 80:
                      color = Fore.YELLOW
                else:
                    color = Fore.RED

                linea = ("\r"f"{Style.BRIGHT if COLORAMA else ''}CPU:{Style.RESET_ALL if COLORAMA else ''} "
                f"{color if COLORAMA else ''}{temp_text}{Style.RESET_ALL if COLORAMA else ''}")

                sys.stdout.write('\r' + linea)             
                sys.stdout.flush()
            else:
                print("No se pudo leer la temperatura")

            time.sleep(1.5)
    except KeyboardInterrupt:
        print("\nLectura finalizada por el usuario")
    finally:
        reader.Dispose()

if __name__ == "__main__":
    main()
