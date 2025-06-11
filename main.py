import clr
import os
import sys
import time

script_dir = os.path.dirname(os.path.abspath(__file__))

# Ruta relativa al DLL
dll_path = os.path.join(
    script_dir,
    "target", "ThermaHUDLib.dll"
)

# Cargamos el ensamblado con AddReference
clr.AddReference(dll_path)

try:
    from ThermaHUDLib import ThermaHUD # type: ignore
except Exception as e:
    print("ERROR al importar ThermaHUDLib:", e)
    sys.exit(1)

reader = ThermaHUD()
try:
    while True:
        temp = reader.GetCpuTemperature()
        if temp is not None:
            print(f"Temp CPU: {temp:.1f} °C")
        else:
            print("No se pudo leer la temperatura")
        time.sleep(1)
except KeyboardInterrupt:
    print("\nLectura finalizada por el usuario.")
