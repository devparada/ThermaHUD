using System;
using System.Linq;
using System.Collections.Generic;
using LibreHardwareMonitor.Hardware;

namespace ThermaHUDLib
{
    public class ThermaHUD : IVisitor
    {
        private static readonly Computer computer = new Computer { IsCpuEnabled = true };
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

        private List<SensorInfo> GetTemperatureSensors(ICollection<ISensor> sensors)
        {
            return sensors
                .Where(s => s.SensorType == SensorType.Temperature)
                .Select(s => new SensorInfo(s.Name, s.Value))
                .ToList();
        }

        public float? GetCpuTemperature()
        {
            cpuTemperature = null;
            computer.Accept(this);
            return cpuTemperature;
        }
        public List<SensorInfo> GetCpuTemperatureSensors()
        {
            var sensors = new List<SensorInfo>();

            foreach (var hardware in computer.Hardware)
            {
                if (hardware.HardwareType != HardwareType.Cpu)
                    continue;

                hardware.Update();

                foreach (var sensor in hardware.Sensors)
                {
                    if (sensor.SensorType == SensorType.Temperature)
                    {
                        sensors.Add(new SensorInfo(sensor.Name, sensor.Value));
                    }
                }

                foreach (var sub in hardware.SubHardware)
                {
                    sub.Update();

                    foreach (var sensor in sub.Sensors)
                    {
                        if (sensor.SensorType == SensorType.Temperature)
                        {
                            sensors.Add(new SensorInfo(sensor.Name, sensor.Value));
                        }
                    }
                }
            }

            return sensors;
        }

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
                                s.Name.IndexOf("Tctl/Tdie", StringComparison.OrdinalIgnoreCase) >= 0)
                    .ToArray();

                if (tctlSensors.Length > 0)
                {
                    cpuTemperature = tctlSensors.Average(s => s.Value ?? 0f);
                }
            }
        }

        public List<HardwareInfo> GetCpuSensors()
        {
            var result = new List<HardwareInfo>();

            foreach (var hardware in computer.Hardware)
            {
                if (hardware.HardwareType != HardwareType.Cpu)
                    continue;

                hardware.Update();
                var hwInfo = new HardwareInfo(hardware.Name)
                {
                    Sensors = GetTemperatureSensors(hardware.Sensors)
                };

                foreach (var sub in hardware.SubHardware)
                {
                    sub.Update();
                    var subInfo = new SubHardwareInfo(sub.Name)
                    {
                        Sensors = GetTemperatureSensors(sub.Sensors)
                    };
                    hwInfo.SubHardwares.Add(subInfo);
                }

                result.Add(hwInfo);
            }

            return result;
        }

        public void Dispose()
        {
            if (isInitialized)
            {
                computer.Close();
                isInitialized = false;
            }
        }

        public void VisitSensor(ISensor sensor) { }

        public void VisitParameter(IParameter parameter) { }
    }
}
