using System;
using System.Linq;
using LibreHardwareMonitor.Hardware;

namespace ThermaHUDLib
{
    public class ThermaHUD : IVisitor
    {
        private float? cpuTemperature = null;

        public float? GetCpuTemperature()
        {
            cpuTemperature = null;
            var computer = new Computer { IsCpuEnabled = true };

            try
            {
                computer.Open();
                computer.Accept(this);
            }
            finally
            {
                computer.Close();
            }

            return cpuTemperature;
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

        public void VisitSensor(ISensor sensor) { }

        public void VisitParameter(IParameter parameter) { }
    }
}
