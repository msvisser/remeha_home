# Clock program schedules

The Clock program sensors of the climate zones and hot water zones show the active clock program, and have its week schedule as the `schedule` attribute.
The schedule has the same shape for heating and hot water: per day, Monday first, a list of switching points with the time, the mode from then on, and its setpoint.

```yaml
program: 1
schedule:
  monday:
    - {time: "06:30", mode: "Home", setpoint: 20.0}
    - {time: "22:30", mode: "Sleep", setpoint: 18.0}
  tuesday: ...
```

- Each switching point gives the mode from that time on. A day starts with the mode of the last switching point of the day before, as in the Remeha Home app.
- For heating, the mode is the name of the activity and the setpoint its temperature, as in the Remeha Home app.
- For hot water, the mode is Comfort or Eco, with the comfort or eco temperature of the hot water zone. A combi boiler doesn't keep water warm in Eco, so it has no Eco setpoint.
- The schedule is read every 15 minutes, and right away when another clock program becomes active, so changes made in the Remeha Home app show up. It is read-only.
- The schedule isn't stored in the history database, because it is large and rarely changes.


To show a schedule on a dashboard, use a Markdown card with a template. Examples for heating and hot water are in [examples/cards/clock_program_schedule.yaml](../examples/cards/clock_program_schedule.yaml). Replace the entity IDs with those of your sensors.
