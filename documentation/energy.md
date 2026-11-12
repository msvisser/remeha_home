# Energy

The energy sensors are listed in [Entities](entities.md). This page explains where the values come from, and how to look back at earlier days.

## Energy sensors

If the heat pump and gas boiler of a hybrid report the same instance number,
the gas boiler gets a separate device. Existing IDs are kept when possible;
check sensor names, units and history after updating.

The energy values come from Remeha and are updated every 15 minutes. Remeha only reports them with a delay of about 2 hours, and right after midnight the values of the new day start at 0.
On hybrid setups where the existing gas boiler heats the hot water, such as the Remeha Elga Ace, Remeha does not report the gas used for hot water, so that sensor stays at 0.
Most of that gas is missing from the Remeha data, and some of it may show up as gas for heating.

On a hybrid system, the energy consumed by the appliance as a whole is the electricity of the heat pump plus the gas of the gas boiler, both in kWh.
For the [Energy dashboard](https://www.home-assistant.io/docs/energy/), use the sensors of the producers instead: the heat pump's energy consumed as electricity, and the gas boiler's gas in m³ as gas.

## Read-only energy history

The read-only `remeha_home.get_energy_history` action retrieves Remeha's daily
**space-heating** energy estimates for up to 366 inclusive local calendar days.
Choose a Remeha appliance or producer in **Developer tools → Actions**:

```yaml
action: remeha_home.get_energy_history
data:
  device_id: "<select your Remeha device in the visual editor>"
  start_date: "2026-01-01"
  end_date: "2026-01-31"
```

Only whole days are returned. Remeha keeps adding to today's figures until
midnight, so the period ends yesterday at the latest: an `end_date` of today or
later is shortened to yesterday, and `end_date` in the response shows the last
day that is included. A period that starts today or later is rejected.

The response contains daily heat-pump electricity and delivered heat in kWh,
daily indicative heating COP, gas heating energy in kWh, and an energy-weighted
COP over reported days. A flag indicates whether the requested period is
complete. The API's gas kWh differ from the m³ shown by the existing gas
sensors. Remeha's figures are **estimates**, not independently metered
values. No entities or Home Assistant statistics are changed.
