import clr
import ctypes
import os
import sys
import shutil
import tempfile
import time

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
            val = f"{sensor.Value:.1f}" if sensor.Value is not None else "N/A"
            print(f"  Sensor: {sensor.Name} -> {val} °C")
        for sub in hw.SubHardwares:
            print(f"  SubHardware: {sub.Name}")
            for sensor in sub.Sensors:
                val = f"{sensor.Value:.1f}" if sensor.Value is not None else "N/A"
                print(f"    Sensor: {sensor.Name} -> {val} °C")
        print()  # línea vacía

def resource_path(relative_path):
    # Detecta la ruta base donde están las DLLs originales
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.abspath(os.path.join(base_path, "..", relative_path))

def main():
    # Rutas DLLs
    bundled_dll_path = resource_path("target/ThermaHUDLib.dll")
    bundled_dep_dll_path = resource_path("lib/LibreHardwareMonitorLib.dll")

    # Crear carpeta temporal para DLLs y copia de las DLLs
    temp_dir = tempfile.mkdtemp(prefix="thermahud_")
    shutil.copyfile(bundled_dll_path, os.path.join(temp_dir, "ThermaHUDLib.dll"))
    shutil.copyfile(bundled_dep_dll_path, os.path.join(temp_dir, "LibreHardwareMonitorLib.dll"))

    # Añade la carpeta temporal al PATH para que Windows encuentre las DLLs dependientes
    os.environ["PATH"] = temp_dir + os.pathsep + os.environ.get("PATH", "")
    add_dll_directory(temp_dir)

    extracted_dll_path = os.path.join(temp_dir, "ThermaHUDLib.dll")

    try:
        ctypes.CDLL(extracted_dll_path)
    except Exception as e:
        print(f"[WARNING] No se pudo cargar DLL con ctypes: {e}")

    try:
        clr.AddReference(extracted_dll_path)
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
                print(f"Temp CPU: {temp:.1f} °C")
            else:
                print("No se pudo leer la temperatura")
            time.sleep(2)
    except KeyboardInterrupt:
        print("\nLectura finalizada por el usuario")

if __name__ == "__main__":
    main()
