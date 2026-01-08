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
- **Forecast-Aware**: Caches hourly weather forecast for energy predictions and services

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
4. Select four inputs:
   - **Energy Sensor**: Cumulative energy consumption (kWh)
   - **Running Sensor**: Binary sensor indicating when heat pump is running
   - **Temperature Sensor**: Outdoor temperature sensor (°C)
  - **Weather Entity**: Weather entity that exposes hourly forecasts (used for predictions)
5. Click **Submit**

### Required Inputs

The integration requires three sensors from your heat pump system:

#### 1. Energy Sensor
- **Type**: `sensor` with `device_class: energy`
- **Unit**: kWh (kilowatt-hours)
- **State Class**: Must be `total_increasing` (cumulative meter)
- **Requirements**:
  - Must be a monotonically increasing counter
  - Should track **only** your heat pump's energy consumption
  - Must have numeric state (not "unavailable" or "unknown")
- **Examples**:
  - `sensor.heat_pump_energy`
  - `sensor.inverter_total_energy`
  - Shelly EM energy counter
  - Modbus energy register from heat pump
- **How to get**: Install an energy monitoring device (Shelly EM, CT clamp meter, smart plug with energy monitoring) on your heat pump circuit, or use built-in energy reporting if your heat pump supports it.

#### 2. Running Sensor
- **Type**: `binary_sensor`
- **States**: `on` (heat pump running) / `off` (heat pump idle)
- **Requirements**:
  - Must accurately reflect when the compressor is actively running
  - Should update immediately when heat pump starts/stops
  - Not just "system enabled" - must indicate actual operation
- **Examples**:
  - `binary_sensor.heat_pump_compressor`
  - `binary_sensor.heat_pump_running`
  - Current sensor threshold template (e.g., >1A = running)
  - Heat pump's built-in status output
- **How to get**: 
  - Use a current sensor (CT clamp) with threshold (e.g., create template: `{{ states('sensor.heat_pump_current')|float > 1 }}`)
  - Use heat pump's digital output if available
  - Create template from power sensor: `{{ states('sensor.heat_pump_power')|float > 100 }}`
  - Some smart plugs provide binary "running" state

#### 3. Temperature Sensor
- **Type**: `sensor` with `device_class: temperature`
- **Unit**: °C (Celsius)
- **Requirements**:
  - Must measure **outdoor** temperature (not indoor)
  - Should be placed where heat pump reads outdoor temp (near outdoor unit)
  - Must have numeric state
  - Should update at least every 5-10 minutes
- **Examples**:
  - `sensor.outdoor_temperature`
  - Weather station sensor
  - Heat pump's built-in outdoor temp sensor
  - Smart thermometer near outdoor unit
- **How to get**:
  - Use weather integration (e.g., Met.no, OpenWeatherMap)
  - Install outdoor temperature sensor (Zigbee, Z-Wave, ESPHome)
  - Read from heat pump if it exposes outdoor temp via Modbus/API
  - **Important**: Weather API temps may differ from your actual location - using a sensor near your heat pump gives more accurate results

#### 4. Weather Entity
- **Type**: `weather` entity
- **Purpose**: Provides hourly forecast data so the integration can estimate future energy use via the forecast cache sensor and `calculate_forecast_energy` service
- **Requirements**:
  - Must support the `weather.get_forecasts` service with `type: hourly`
  - Should provide hourly temperatures in °C for at least 24–48 hours ahead
  - Must be available in Home Assistant (not `unavailable`/`unknown`)
- **Examples**:
  - `weather.home`
  - `weather.openweathermap`
  - `weather.met_no`
  - Any other provider that exposes hourly forecasts
- **How to get**: Add a weather integration that offers hourly forecasts (e.g., Met.no, OpenWeatherMap, NWS) and pick its weather entity during setup

## Usage

After configuration, the integration creates:

### Temperature-Specific Sensors (224 total, disabled by default)
- `sensor.heat_pump_predictor_total_energy_<temp>`
- `sensor.heat_pump_predictor_avg_power_running_<temp>`
- `sensor.heat_pump_predictor_avg_power_overall_<temp>`
- `sensor.heat_pump_predictor_duty_cycle_<temp>`

Where `<temp>` ranges from -25 to 30°C.

Enable sensors for temperatures relevant to your climate. For example, if you typically experience 0°C to 15°C:
- `sensor.heat_pump_predictor_total_energy_0`
- `sensor.heat_pump_predictor_avg_power_running_5`
- `sensor.heat_pump_predictor_duty_cycle_10`

### Performance Curve Sensors (enabled by default)

The integration automatically creates three sensors with chart-ready data:

#### 1. Power Curve (`sensor.heat_pump_predictor_power_curve`)
- **Purpose**: Shows power consumption across all temperatures
- **Data**: `{temp, power_overall, power_running}` for each temperature
- **Use**: Visualize how power consumption changes with outdoor temperature

#### 2. Duty Cycle Curve (`sensor.heat_pump_predictor_duty_cycle_curve`)
- **Purpose**: Shows duty cycle percentage across all temperatures
- **Data**: `{temp, duty_cycle}` for each temperature
- **Use**: Identify at what temperatures your heat pump struggles (high duty cycle)

#### 3. Energy Distribution (`sensor.heat_pump_predictor_energy_distribution`)
- **Purpose**: Shows total energy consumed at each temperature
- **Data**: `{temp, energy}` for each temperature
- **Use**: Determine which temperatures cost you the most to heat

These sensors update automatically whenever bucket data changes and only include temperatures with actual data.

### Weather forecast refresh

- The hourly forecast cache sensor pulls the selected weather entity immediately on startup/addition, then every 30 minutes.
- Reloading the integration or restarting Home Assistant triggers the initial refresh again.
- To change which weather entity is used, rerun the config/options flow and select the new weather entity.

### Scheduled forecast sensors

Three forecast sensors run daily using the cached forecast and store `total_energy_kwh` with detailed `hours` attributes:

- Morning window: runs at 04:00, calculates starting at hour 6 for 7 hours.
- Afternoon window: runs at 13:00, calculates starting at hour 15 for 7 hours.
- Daily window: runs at 23:55, calculates starting at hour 0 for 24 hours.

Ensure the hourly forecast cache is available so these sensors remain updated and available.

## Services

Two response-only services expose the predictor calculations without creating extra entities:

- `heat_pump_predictor.calculate_energy`
  - **Purpose**: Estimate per-hour energy use at a specific outdoor temperature bucket.
  - **Params**: `temperature` (float, -25 to 30), optional `config_entry_id` when multiple entries exist.
  - **Returns**: `energy_kwh` (per hour), `power_running_w`, `power_overall_w`, `duty_cycle_percent`, `temperature_bucket`, `confidence` (`high|medium|low|approximated`), `approximated` flag, `approximation_source` (bucket used), `data_points_hours`.
  - **Notes**: Uses collected bucket data; if none exists for that bucket it falls back to the closest bucket and marks `approximated`.

- `heat_pump_predictor.calculate_forecast_energy`
  - **Purpose**: Predict energy for an hourly forecast window using the cached weather forecast and bucket models.
  - **Params**: `starting_hour` (0–23, local), `hours_ahead` (1–48), optional `config_entry_id` when multiple entries exist.
  - **Returns**: `total_energy_kwh`, per-hour array `hours` with `datetime`, `temperature`, optional `temperature_delta`, `trend_adjustment`, `energy_kwh`, `confidence`, `approximated`, `approximation_source`, plus `hours_requested`, `hours_returned`, `approximated_hours`, `starting_hour`.
  - **Notes**: Requires the hourly forecast cache sensor to have data; applies a trend adjustment when temperatures rise/fall hour to hour.

### Quick service examples

- Developer Tools → Services → `heat_pump_predictor.calculate_energy`
  ```yaml
  temperature: 5
  ```

- Developer Tools → Services → `heat_pump_predictor.calculate_forecast_energy`
  ```yaml
  starting_hour: 6
  hours_ahead: 12
  ```

## Sensor Types Explained

The integration creates **4 sensor types** for each temperature bucket:

### 1. Energy (kWh)
- **What**: Total cumulative energy consumed when outdoor temperature was at this specific degree
- **State Class**: `TOTAL_INCREASING` (compatible with Energy Dashboard)
- **Example**: "Energy at 5°C" = 45.3 kWh
- **Use**: Track how much total electricity your heat pump has consumed at each outdoor temperature over time. Helps identify which temperatures cost the most to heat.

### 2. Running Power (W)
- **What**: Average power consumption **while the heat pump was actively running** at this temperature
- **State Class**: `MEASUREMENT`
- **Example**: "Running power at 5°C" = 2500 W
- **Use**: Shows how hard the heat pump works when it's actually on. Higher values at colder temps = heat pump works harder. This is the "intensity" when running.

### 3. Overall Power (W)
- **What**: Average power consumption **including both running and idle time** at this temperature
- **State Class**: `MEASUREMENT`
- **Example**: "Overall power at 5°C" = 1200 W (if duty cycle is 48%)
- **Use**: Real-world average power draw. If duty cycle is 50% and running power is 2500W, overall is ~1250W. Better for calculating actual costs.

### 4. Duty Cycle (%)
- **What**: Percentage of time the heat pump was running vs. idle at this temperature
- **State Class**: `MEASUREMENT`
- **Precision**: 2 decimal places
- **Example**: "Duty cycle at 5°C" = 48.35%
- **Use**: Shows how often the heat pump needs to run. 100% = running constantly (undersized or very cold). 20% = cycles occasionally. Helps identify optimal operating temperatures.

### Relationship Between Metrics

```
Overall Power ≈ Running Power × (Duty Cycle / 100)
Energy = Power × Time at each temperature
```

### Practical Example

At **-5°C**:
- **Energy**: 12.5 kWh total consumed at this temperature
- **Running Power**: 3200 W when compressor is on
- **Overall Power**: 2560 W average (including idle)
- **Duty Cycle**: 80% → heat pump runs 80% of the time

**Interpretation**: At -5°C, your heat pump works hard (3200W) and barely stops (80% duty cycle), consuming significant energy. You could use this to predict costs for cold weather or decide if your system is sized correctly.

## How It Works

### Temperature Bucketing

Outdoor temperatures are bucketed using floor function:
- 4.9°C → Bucket 4
- 5.0°C → Bucket 5
- -0.1°C → Bucket -1

### Previous-State Attribution

Energy consumption is attributed to the temperature bucket where the heat pump **was operating**, not where it transitioned to. This ensures accurate performance tracking at each temperature.

### Power Calculations

The integration tracks three key metrics per temperature bucket:
1. **`total_energy_kwh`** - Total energy consumed at this temperature
2. **`total_time_seconds`** - Total time spent at this temperature
3. **`running_time_seconds`** - Time heat pump was running at this temperature

#### Running Power

```
Running Power = (total_energy_kwh × 1000) / (running_time_seconds / 3600)
```

**Example:**
- Temperature: 5°C
- Total energy consumed: 3.5 kWh
- Running time: 2 hours (7200 seconds)

```
Running Power = (3.5 × 1000) / (7200 / 3600)
              = 3500 / 2
              = 1750 W
```

**Meaning**: When the heat pump was actually ON at 5°C, it consumed an average of 1750W.

#### Overall Power

```
Overall Power = (total_energy_kwh × 1000) / (total_time_seconds / 3600)
```

**Example (same scenario):**
- Temperature: 5°C
- Total energy consumed: 3.5 kWh
- **Total time at 5°C**: 5 hours (18000 seconds)
- Running time: 2 hours (7200 seconds)

```
Overall Power = (3.5 × 1000) / (18000 / 3600)
              = 3500 / 5
              = 700 W
```

**Meaning**: Over the entire 5 hours at 5°C, the heat pump averaged 700W (including idle time).

#### Verification

```
Duty Cycle = (running_time_seconds / total_time_seconds) × 100
           = (7200 / 18000) × 100
           = 40%

Overall Power = Running Power × (Duty Cycle / 100)
              = 1750 × 0.40
              = 700 W ✓
```

#### Data Accumulation

Every coordinator update:
1. Calculate time elapsed since last update
2. Calculate energy consumed (delta from energy sensor)
3. **Attribute to PREVIOUS temperature bucket** (where heat pump was operating)
4. Add time elapsed to `total_time_seconds`
5. If heat pump was running, add:
   - Time to `running_time_seconds`
   - Energy delta to `total_energy_kwh`

The metrics accumulate over the integration's lifetime, providing increasingly accurate averages as more data is collected at each temperature.

### Data Updates

- **Immediate**: State changes trigger instant updates
- **Periodic**: 5-minute polling ensures data consistency
- **Persistence**: Data is saved to disk and survives Home Assistant restarts
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
