# Entities

The entities that the integration creates, per climate zone, hot water zone, appliance and heat source.

- All climate zones are exposed as [climate](https://www.home-assistant.io/integrations/climate/) entities with:
    - The following modes:
        - Auto mode: the thermostat will follow the clock program.
        If the target temperature is changed, it will temporarily override the clock program until the next target temperature change in the schedule.
        - Heat mode: the thermostat will be set to manual mode and continuously hold the set temperature.
        For a zone that can cool this mode is shown as Heat/Cool, because Remeha uses the same manual mode for heating and cooling.
        A zone can cool when it reports so (`capabilityCooling`) or has Cooling activities; any other zone shows Heat.
        - Off mode: the thermostat is set to frost protection.
        A temperature can't be set in this mode: change the mode first, or pass `hvac_mode` together with the temperature in `climate.set_temperature`.
    - Presets for the three clock programs available in the Remeha Home app (Schedule 1 to 3), and for Manual and Frost protection.
    When a clock program is selected, the integration will automatically switch the climate zone to auto mode to make sure the preset is applied.
    Manual is the same as heat (or heat/cool) mode, with the current target temperature, and Frost protection is the same as off mode.
    In heat (or heat/cool) mode the preset shows Manual, in off mode Frost protection.
    - An action to hold another temperature for a while, after which the zone returns to its clock program. See [Temporary temperature](temporary-temperature.md).
- Each climate zone also exposes the following sensors/switches/numbers:
    - The room temperature
    - The status (e.g. heating or idle), plus a binary status sensor (disabled by default)
    - Pre-heat (binary sensor, if reported by the appliance): on while the zone starts heating early to reach the next setpoint of the clock program on time
    - The next schedule setpoint
    - The time at which the next schedule setpoint gets activated
    - The active clock program (diagnostic), with the week schedule of that program as an attribute. See [Clock program schedules](clock-programs.md).
    - The current schedule setpoint, as Remeha reports it. Right after a switch of the clock program it can still show the setpoint of the previous program for a while.
    - The end time of a temporary override (unknown when there is none), also as the `override_end_time` attribute of the climate entity
    - Switch to control fireplace mode
    - The heating curve slope and base setpoint (if supported by the appliance), and its maximum flow temperature (diagnostic).
    They are updated every 15 minutes, so changes made in the Remeha Home app show up.
    - The temperatures of the heating activities used in the clock programs.
    They are updated every 15 minutes, so changes made in the Remeha Home app show up. After a change in Home Assistant, the next update is 15 minutes later, because Remeha can still answer with the old values right after a change.
- Each hot water zone exposes:
    - The water temperature. Combi boilers that don't report it get no water temperature sensor.
    - The current activity (Comfort or Eco)
    - The status, plus a binary status sensor (both disabled by default)
    - The time at which the next schedule setpoint gets activated, and the next activity of the clock program (Comfort or Eco). The API also reports both when the zone doesn't follow the clock program, e.g. in Eco mode.
    - The number of the active hot water clock program (diagnostic), shown with the names of the presets of the climate entity (Schedule 1 to 3), with the week schedule of that program as an attribute. See [Clock program schedules](clock-programs.md).
    - Whether hot water optimization is enabled (binary sensor, diagnostic, if supported by the appliance)
    - Water heater control with modes (Schedule, Comfort, Eco) and target temperature, the same modes as in the Remeha Home app.
    The target temperature is the setpoint of the active activity, Comfort or Eco.
    - Setpoint numbers for the Comfort and Eco temperatures. The Eco temperature is only available for a hot water tank: a combi boiler doesn't keep water warm in Eco, so Remeha has no Eco temperature for it.
    - A Boost switch to start and stop boost (if supported by the appliance). Remeha only accepts boost while the zone is in Schedule mode, so the switch gives an error in other modes. Stopping boost returns the zone to Schedule. While boosting, the water heater shows the Boost mode and its `remaining_boost_time` attribute shows how long it still runs.
- Each appliance (boiler or heat pump) exposes the following sensors:
    - The water pressure, and a Water Pressure problem sensor that turns on when Remeha reports that the pressure is not OK
    - Whether the appliance is online (diagnostic)
    - The thermal mode (e.g. heating, cooling or idle)
    - The operating mode (e.g. AutomaticHeating): what the appliance is set to do, where the thermal mode shows what it is doing now
    - The error status reported by Remeha (e.g. Running)
    - The outdoor temperature measured by the appliance, and the outdoor temperature from the Remeha cloud (disabled by default)
    - Holiday mode (binary sensor), with the scheduled `start_date` and `end_date` as attributes, and actions to schedule and cancel a holiday. After a holiday, the integration sets the zones back to their modes. See [Holiday mode](holiday-mode.md).
    - The energy consumed and delivered today for heating, hot water and cooling, for the appliance as a whole (disabled by default)
- Each producer (heat source) of an appliance, such as the heat pump and the gas boiler of a hybrid system, is a separate device with:
    - For heat pumps (and other electric producers): the energy consumed and delivered today for heating, hot water and cooling, and the seasonal efficiency
    - For gas boilers: the gas used today for heating and hot water, in m³

    See [Energy](energy.md) for what these values mean, and which ones to use for the Energy dashboard.
