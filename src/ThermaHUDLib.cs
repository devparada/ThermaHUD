using System;
using System.Linq;
using System.Collections.Generic;
using LibreHardwareMonitor.Hardware;

namespace ThermaHUDLib
{
    public class ThermaHUD : IVisitor, IDisposable
    {
        private static readonly Computer computer = new()
        {
            IsCpuEnabled = true
        };

        private float? cpuTemperature = null;
        private static bool isInitialized = false;

        public ThermaHUD()
        {
            if (!isInitialized)
            {
                computer.Open();
                isInitialized = true;
            }
        }

        private static List<SensorInfo> GetTemperatureSensors(ICollection<ISensor> sensors)
        {
            return [.. sensors
                .Where(s => s.SensorType == SensorType.Temperature)
                .Select(s => new SensorInfo(s.Name, s.Value))];
        }

        // --- API LibreHardwareMonitorLib ---

        public float? GetCpuTemperature()
        {
            cpuTemperature = null;
            computer.Accept(this);
            return cpuTemperature;
        }
        public List<SensorInfo> GetCpuTemperatureSensors()
        {
            return GetCpuHardware()
                .SelectMany(GetAllTemperatureSensors)
                .ToList();
        }

        public List<HardwareInfo> GetCpuSensors()
        {
            return GetCpuHardware()
                .Select(hw =>
                {
                    var hwInfo = new HardwareInfo(hw.Name)
                    {
                        Sensors = GetTemperatureSensors(hw.Sensors)
                    };

                    foreach (var sub in hw.SubHardware)
                    {
                        sub.Update();
                        hwInfo.SubHardwares.Add(new SubHardwareInfo(sub.Name)
                        {
                            Sensors = GetTemperatureSensors(sub.Sensors)
                        });
                    }

                    return hwInfo;
                }).ToList();
        }

        // --- Métodos privados ayudantes ---

        private static IEnumerable<IHardware> GetCpuHardware()
        {
            return computer.Hardware.Where(h => h.HardwareType == HardwareType.Cpu);
        }

        private List<SensorInfo> GetAllTemperatureSensors(IHardware hardware)
        {
            hardware.Update();
            var result = GetTemperatureSensors(hardware.Sensors);

            foreach (var sub in hardware.SubHardware)
            {
                sub.Update();
                result.AddRange(GetTemperatureSensors(sub.Sensors));
            }

            return result;
        }

        // --- Implementación de IVisitor ---

        public void VisitComputer(IComputer computer)
        {
            computer.Traverse(this);
        }

        public void VisitHardware(IHardware hardware)
        {
            hardware.Update();
            foreach (var sub in hardware.SubHardware)
                sub.Accept(this);

            if (hardware.HardwareType == HardwareType.Cpu)
            {
                var tctlSensors = hardware.Sensors
                    .Where(s => s.SensorType == SensorType.Temperature &&
                           s.Name != null &&
                           (s.Name.ToLowerInvariant().Contains("tctl") ||
                            s.Name.ToLowerInvariant().Contains("core")))
                    .ToArray();

                if (tctlSensors.Length > 0)
                {
                    cpuTemperature = tctlSensors.Average(s => s.Value ?? 0f);
                }
            }
        }

        public void VisitSensor(ISensor sensor) { }
        public void VisitParameter(IParameter parameter) { }

        // --- Limpieza de recursos ---

        public void Dispose()
        {
            if (isInitialized)
            {
                computer.Close();
                isInitialized = false;
            }

            GC.SuppressFinalize(this);
        }
    }
}
