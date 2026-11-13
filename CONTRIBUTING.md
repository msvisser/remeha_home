# Contributing

Thanks for helping out. This document explains how the integration works, how to set up a development environment, and what a pull request needs.

To report a bug or request a feature, [open an issue](https://github.com/hugo-leij/remeha_home/issues/new/choose).

## How the integration works

The integration talks to the Remeha Home cloud API of BDR Thermea, the same API that the Remeha Home app uses.
There is no local connection to the appliance.
The [API documentation](documentation/api.md) describes the calls and responses.

| File | What it does |
| --- | --- |
| `__init__.py` | Sets up the integration: the login, the coordinator, the devices and the platforms |
| `config_flow.py` | Logs in with a Remeha Home account, and asks to log in again when the token can't be refreshed |
| `api.py` | `RemehaHomeAPI` has one method per API call. `RemehaHomeOAuth2Implementation` handles the OAuth2 login |
| `coordinator.py` | Fetches the data, see below, and lets the entities look it up by id |
| `climate.py`, `water_heater.py`, `sensor.py`, `binary_sensor.py`, `switch.py`, `number.py` | The entities of each platform |
| `const.py` | The descriptions of the sensors and binary sensors |
| `util.py` | Helpers, such as reading the times of the API |
| `holiday.py` | Sets the zones back to their modes after a holiday |
| `diagnostics.py` | The diagnostics download, with personal data redacted |
| `services.yaml` | The holiday mode actions |
| `translations/` | Names and messages in English, French, Dutch and Polish |

The coordinator fetches:
- the dashboard every 60 seconds: the appliances with their climate zones and hot water zones;
- the technical information and the activities once, and the activities again after a change;
- the energy consumption and the heating curve every 15 minutes.

Each appliance is a device.
Its climate zones, hot water zones and producers (such as the heat pump and the gas boiler of a hybrid system) are separate devices linked to it.

Some things to know:
- An entity finds its data with `coordinator.get_by_id(item_id)`, where `item_id` is the id of the appliance or zone.
- The `key` of a sensor description in `const.py` is the field in the API response. A dot goes one level deeper, e.g. `outdoorTemperatureInformation.applianceOutdoorTemperature`.
- Unique ids look like `remeha_home_<id>_<key>`. Don't change them: users would get new entities and lose their history.
- Most times from the API are local times with a `Z` suffix, but some are in UTC. Use `util.remeha_time()` and `util.remeha_utc_time()`; see [Times](documentation/api.md#times).
- The diagnostics contain the data that the coordinator holds. When you store new data that can identify a person or an appliance, such as a name or a serial number, add its key to `TO_REDACT` in `diagnostics.py`.
- A user's diagnostics download shows what their appliance returns. With the ids anonymized, its API responses can become a test fixture; the [README](README.md#diagnostics) says which parts are API responses and what the integration adds.

## Development environment

### Dev container (recommended)

You need [VS Code](https://code.visualstudio.com/) with the [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) extension, and Docker (for example Docker Desktop, Colima or OrbStack).

1. Open the repository in VS Code and run **Dev Containers: Reopen in Container**.
   The first time this takes a few minutes: `scripts/setup` installs ruff, Home Assistant and the test tools.
2. Run `scripts/develop`, or the task **Run Home Assistant on port 8123**.
3. Open http://localhost:8123, create a user, and add the Remeha Home integration with your Remeha Home account.

Notes:
- `config/` holds the configuration of this Home Assistant. Git ignores everything in it except `configuration.yaml`, so your login stays local.
- Debug logging for the integration is on, see `config/configuration.yaml`.
- After changing the code, stop Home Assistant with Ctrl+C and run `scripts/develop` again.
- The log shows errors about ffmpeg, go2rtc, libturbojpeg and libpcap. They come from the default integrations of Home Assistant, which need programs that aren't in the container, and don't affect this integration.

### Without the dev container

Use Python 3.14:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt -r requirements_test.txt
scripts/develop
```

### On your own Home Assistant

Copy `custom_components/remeha_home` to the `custom_components` folder of your Home Assistant configuration, and restart Home Assistant.

## Tests and lint

The tests and lint run on every pull request. To run them yourself (Python 3.14):

```bash
python3 -m pip install -r requirements_test.txt
python3 -m pytest
ruff check .
```

- The tests use [pytest-homeassistant-custom-component](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component).
  The API is replaced by a mock that answers with the responses in `tests/fixtures`.
- `tests/conftest.py` has fixtures for the dashboard, its appliance and zones, and helpers to set up the integration (`setup_integration`), fetch the data again (`refresh`) and find an entity (`entity_id`).
  A test can change the dashboard before the setup or before a refresh.
- `scripts/lint` runs ruff and fixes what it can.
  The code isn't formatted with `ruff format`, so don't reformat files you don't change.
- Never commit personal data, such as ids, names, serial numbers or e-mail addresses.
  Anonymize API responses before you add them to `tests/fixtures`.

## Pull requests

- Start from `main`, and keep each pull request to one topic.
- Add or update tests. A fix comes with a test that fails without the fix.
- When you add or change a text in `translations/en.json`, do the same in all other files in `translations/`. If you can't translate it, say so in the pull request.
- Update the README when entities or behaviour change, and `documentation/api.md` when you use a new API call.
- Write code, comments, commits and pull requests in English.
- The checks Pytest, Ruff, Hassfest Validation and HACS Validation must pass before a pull request can be merged.

Dependabot opens a weekly pull request for the GitHub Actions and one for the Python requirements.

## Releases (maintainers)

1. Publish a release in the GitHub UI with a new tag `v0.x.y` on `main`: a new minor version for new features, a new patch version for fixes only.
   Release notes have the sections New, Improvements or Fixes, Breaking changes when needed, and Thanks.
2. The Release workflow adds `remeha_home.zip` to the release, with the tag as the version in its `manifest.json`. HACS installs from that zip. In the repository the version stays `0.0.0`, so don't change it by hand.
3. Check that the Release workflow passed and that the zip is attached.
