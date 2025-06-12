using System.Collections.Generic;

namespace ThermaHUDLib
{
    public class SensorInfo(string name, float? value)
    {
        public string Name { get; } = name;
        public float? Value { get; } = value;
    }

    public class SubHardwareInfo
    {
        public string Name { get; set; }
        public List<SensorInfo> Sensors { get; set; }

        public SubHardwareInfo(string name)
        {
            Name = name;
            Sensors = [];
        }
    }

    public class HardwareInfo(string name)
    {
        public string Name { get; set; } = name;
        public List<SensorInfo> Sensors { get; set; } = [];
        public List<SubHardwareInfo> SubHardwares { get; set; } = [];
    }
}
