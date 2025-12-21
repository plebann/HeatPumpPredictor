# Heat Pump Predictor

A Home Assistant custom integration that tracks heat pump performance across different outdoor temperatures.

## Features

- **Temperature Bucket Tracking**: Monitors performance across 56 temperature buckets (-25°C to 30°C)
- **Multiple Metrics**: Tracks 4 key metrics per temperature bucket:
  - Total energy consumed (kWh)
  - Average power when running (W)
  - Average power overall (W)
  - Duty cycle (%)
- **Hybrid Updates**: Combines 5-minute polling with immediate state change tracking
- **Previous-State Attribution**: Accurately attributes energy consumption to the temperature where it occurred
- **224 Dynamic Sensors**: Creates entities for all temperature/metric combinations
- **Long-Term Statistics**: Integrates with Home Assistant recorder for historical data

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL and select "Integration" as the category
6. Click "Install"
7. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/heat_pump_predictor` directory to your Home Assistant `custom_components` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for "Heat Pump Predictor"
4. Select three entities:
   - **Energy Sensor**: Cumulative energy consumption (kWh)
   - **Running Sensor**: Binary sensor indicating when heat pump is running
   - **Temperature Sensor**: Outdoor temperature sensor (°C)
5. Click **Submit**

## Usage

After configuration, 224 sensors will be created (disabled by default):
- `sensor.heat_pump_predictor_total_energy_<temp>`
- `sensor.heat_pump_predictor_avg_power_running_<temp>`
- `sensor.heat_pump_predictor_avg_power_overall_<temp>`
- `sensor.heat_pump_predictor_duty_cycle_<temp>`

Where `<temp>` ranges from -25 to 30°C.

Enable sensors for temperatures relevant to your climate. For example, if you typically experience 0°C to 15°C:
- `sensor.heat_pump_predictor_total_energy_0`
- `sensor.heat_pump_predictor_avg_power_running_5`
- `sensor.heat_pump_predictor_duty_cycle_10`

## How It Works

### Temperature Bucketing

Outdoor temperatures are bucketed using floor function:
- 4.9°C → Bucket 4
- 5.0°C → Bucket 5
- -0.1°C → Bucket -1

### Previous-State Attribution

Energy consumption is attributed to the temperature bucket where the heat pump **was operating**, not where it transitioned to. This ensures accurate performance tracking at each temperature.

### Data Updates

- **Immediate**: State changes trigger instant updates
- **Periodic**: 5-minute polling ensures data consistency
- **Statistics**: Home Assistant recorder integration for 60-day retention

## Troubleshooting

### Sensors Show "Unknown"

- Verify all three input sensors are working
- Check that energy sensor has numeric state in kWh
- Ensure running sensor has on/off state
- Confirm temperature sensor has numeric state in °C

### Missing Entities

- Sensors are disabled by default to reduce entity count
- Enable sensors in **Settings** → **Devices & Services** → **Heat Pump Predictor**

### Inaccurate Data

- Verify energy sensor is cumulative (monotonically increasing)
- Check that running sensor accurately reflects heat pump state
- Ensure temperature sensor updates regularly

## License

MIT License - See LICENSE file for details

## Contributing

Contributions are welcome! Please open an issue or pull request on GitHub.

## Support

For issues and feature requests, please use the [GitHub issue tracker](https://github.com/yourusername/HeatPumpPredictor/issues).
