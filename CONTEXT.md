# Heat Pump Predictor

Heat Pump Predictor models how an observed heat pump consumes electricity at different outdoor temperatures, then uses that learned performance profile to estimate future energy use. The context exists to keep the language around measurement, temperature-based attribution, and forecast-based prediction precise.

## Language

### Observed System

**Observed Heat Pump**:
The heat pump whose electricity use, running state, and outdoor conditions are being measured.
_Avoid_: heating system, HVAC unit, device

**Energy Reading**:
A cumulative kWh value for the observed heat pump's electricity consumption.
_Avoid_: power reading, usage sample, meter value

**Running State**:
Whether the observed heat pump is actively running during an observed period.
_Avoid_: enabled state, operating mode, system status

**Outdoor Temperature**:
The outside air temperature used to explain and predict heat pump energy use.
_Avoid_: ambient value, weather temperature, indoor temperature

### Performance Model

**Temperature Bucket**:
A whole-degree outdoor temperature band used to group observed heat pump behavior.
_Avoid_: temperature range, bin, slot

**Bucket Observation**:
The accumulated time and energy attributed to a temperature bucket.
_Avoid_: sample, data point, metric row

**Previous-State Attribution**:
The rule that assigns elapsed time and energy change to the temperature bucket from the prior observation, where the heat pump was operating during that elapsed period.
_Avoid_: current-state attribution, transition attribution, latest-temperature attribution

**Total Time**:
Elapsed observed time in a temperature bucket, including both running and idle periods.
_Avoid_: uptime, runtime, duration

**Running Time**:
Elapsed observed time in a temperature bucket while the observed heat pump was actively running.
_Avoid_: active duration, compressor time, on time

**Duty Cycle**:
The percentage of total time in a temperature bucket during which the observed heat pump was running.
_Avoid_: utilization, load factor, run percentage

**Running Power**:
Average power draw while the observed heat pump was running in a temperature bucket.
_Avoid_: active power, compressor power, peak power

**Overall Power**:
Average power draw across total time in a temperature bucket, including idle periods.
_Avoid_: real-world power, average consumption, blended power

**Energy Distribution**:
The spread of total observed energy across temperature buckets.
_Avoid_: cost distribution, usage chart, energy curve

**Power Curve**:
The temperature-indexed shape of running power and overall power.
_Avoid_: performance chart, power graph, efficiency curve

**Duty Cycle Curve**:
The temperature-indexed shape of duty cycle.
_Avoid_: runtime chart, cycling curve, load curve

### Forecasting

**Hourly Forecast**:
A sequence of future hourly outdoor temperatures used as input for energy prediction.
_Avoid_: weather data, forecast data, weather cache

**Forecast Window**:
The contiguous set of forecast hours included in an energy prediction.
_Avoid_: time range, period, horizon

**Forecast Energy**:
The predicted kWh consumption for a forecast window.
_Avoid_: estimated cost, predicted power, projected usage

**Scheduled Forecast**:
A forecast energy calculation tied to a recurring daily forecast window.
_Avoid_: daily job, scheduled sensor, forecast task

**Trend Adjustment**:
A multiplier applied to forecast energy when the forecast temperature changes from one hour to the next.
_Avoid_: weather correction, slope adjustment, temperature scaling

**Prediction Confidence**:
A qualitative indication of how much observed bucket data supports an energy prediction.
_Avoid_: accuracy, certainty, reliability score

**Approximated Prediction**:
A prediction derived from a nearby temperature bucket because the requested bucket has no direct observations.
_Avoid_: interpolated result, fallback result, guessed estimate

**Approximation Source**:
The temperature bucket whose observations were used to produce an approximated prediction.
_Avoid_: fallback bucket, source bin, nearest sample
