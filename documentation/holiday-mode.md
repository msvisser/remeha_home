# Holiday mode

Like in the Remeha Home app, you can schedule a holiday period. During the holiday, the appliance sets the climate zones to frost protection and turns the hot water off.
In Home Assistant the thermostats then show Off with the preset Frost protection, and the water heater shows Eco, the state it uses for hot water that is off.

- The Holiday Mode binary sensor of the appliance is on while a holiday is active. Its `start_date` and `end_date` attributes show the scheduled period, also before it starts.
- The `remeha_home.set_holiday_mode` action schedules a holiday from `start_date` to `end_date`. Remeha keeps whole days only. The end date is the day you come back: the holiday ends at midnight UTC before that day, which is 01:00 in Central European winter time.
- The `remeha_home.cancel_holiday_mode` action stops an active holiday or removes a scheduled one.
- When the holiday is over, the integration sets the zones back to the modes they had before. See [After the holiday](#after-the-holiday).

Both actions target the Holiday Mode sensor. You can run them from **Developer tools → Actions**, or use them in automations and scripts.
After an action, the dates update right away. The sensor itself only turns on or off a few seconds later, once Remeha has passed the change on to the appliance.

### After the holiday
When the holiday is over, the appliance should set the zones back to the modes they had before.
It doesn't always do that right away: on a Remeha Elga Ace, a zone that followed its clock program sometimes stayed in frost protection for a few minutes.
Other appliances were reported to keep the frost protection setpoint of 6 °C, or to leave the hot water off, until the mode was set again.
So the integration sets the modes back itself:

- When a holiday starts, it saves the mode of each climate zone and hot water zone, as they were at the last update before the holiday. The saved modes are kept when Home Assistant restarts during the holiday.
- When the holiday is over, it sets each zone that is still in frost protection, or hot water that is still off, back to its saved mode:
    - a climate zone to its clock program, or to manual with its saved temperature;
    - the hot water to its schedule, or to comfort.
- A climate zone that followed its clock program is set to it once more, also when it already shows the clock program again, because it can still keep the frost protection setpoint.
- A temporary change of the clock program, and a hot water boost, come back as the plain clock program and schedule.
- A zone that is in another mode after the holiday keeps that mode, for example when you changed it yourself.
  Off is the exception: off is frost protection, the same mode the holiday uses, so a zone that you set to off during the holiday is also set back. The same goes for hot water that you turned off. Turn it off again after the holiday if you want it to stay off.
- It checks the result 15 seconds later, and tries up to three times. If the zones are still not back, it logs a warning.

This works when you cancel the holiday in Home Assistant or in the Remeha Home app, and when the holiday ends by itself.
Home Assistant needs to be running when the holiday starts, because it saves the modes then.
A holiday that ends by itself is over at 01:00 (Central European winter time), so the zones come back at the first update after that, within a minute.


### Example scripts
With these two scripts you can set and cancel a holiday from a dashboard:
- [examples/scripts/set_holiday_mode.yaml](../examples/scripts/set_holiday_mode.yaml) asks for the dates;
- [examples/scripts/cancel_holiday_mode.yaml](../examples/scripts/cancel_holiday_mode.yaml) cancels the holiday.

Create each one in **Settings → Automations & scenes → Scripts → Create script**, choose **Edit in YAML** in the menu (⋮), and paste the YAML.
Replace `binary_sensor.my_home_holiday_mode` with the entity ID of your Holiday Mode sensor.
If you keep your scripts in `scripts.yaml`, put each script under its own key, such as `set_holiday_mode:`.

Add both scripts to a dashboard, for example with an Entities card.
Click the name of Set holiday mode (not its Run button) to open a dialog where you pick the dates and run the script.
Cancel holiday mode only needs its Run button.
