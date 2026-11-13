# Temporary temperature

Like in the Remeha Home app, you can hold another temperature for a while, for example 21 °C for an hour and a half.
The `remeha_home.set_temporary_override` action sets the temperature with an end time on the appliance.
At the end time the appliance returns to the clock program by itself, also when Home Assistant isn't running.

```yaml
action: remeha_home.set_temporary_override
target:
  entity_id: climate.living_room
data:
  temperature: 21
  duration: "01:30:00"
```

- The `duration` is from 1 minute up to 7 days.
- The override lasts until its end time, also past a switch of the clock program. For example, an override of an hour started at 16:50 ends at 17:50, also when the clock program switches at 17:20. After the end time the zone follows the clock program again.
- Changing the zone in the Remeha Home app during the override can change its end time. On a Remeha Elga Ace the end time was moved to the next switch of the clock program.
- The zone must be in auto mode, so following its clock program. In heat or off mode the action asks you to set the zone to auto first.
- During the override the thermostat shows auto, and the end time is in the Override End sensor and the `override_end_time` attribute.
- Running the action again replaces the override. To stop it early, set the zone to heat or off, or select another clock program: the appliance ends the override when the program changes.
- The action needs a zone that reports support for an end time (`capabilityTemporaryOverrideEndTime`). Otherwise it shows an error.

Changing the target temperature in auto mode, for example on the thermostat card, still overrides the clock program until its next switch, as before.

A script that asks for the temperature and the duration is in [examples/scripts/temporary_temperature.yaml](../examples/scripts/temporary_temperature.yaml).
