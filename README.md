# Wing Limiter

[![Marketplace custom repository](https://img.shields.io/badge/Marketplace-Custom-orange.svg)](https://www.home-assistant.io/integrations/marketplace/#custom-repositories)
[![Release](https://img.shields.io/github/v/release/speedy3wk/ha-wing-limiter.svg)](https://github.com/speedy3wk/ha-wing-limiter/releases)
[![Validate](https://github.com/speedy3wk/ha-wing-limiter/actions/workflows/validate.yml/badge.svg)](https://github.com/speedy3wk/ha-wing-limiter/actions/workflows/validate.yml)
[![Tests](https://github.com/speedy3wk/ha-wing-limiter/actions/workflows/tests.yml/badge.svg)](https://github.com/speedy3wk/ha-wing-limiter/actions/workflows/tests.yml)

Control the compressors on the four main buses of a Behringer WING console from Home Assistant over OSC/UDP.

## Features

- Model detection for all four main Dynamics slots. Models are **never switched** by this integration.
- Full standard `COMP` controls and sidechain settings, with model-dependent availability.
- Optional input/output and gain reduction metering, disabled by default.
- Save, list, restore and delete your own persistent compressor profiles.
- Live bus names and English/German UI. Existing compressor/threshold unique IDs are preserved.

## Requirements

- Home Assistant **2026.10.4 or newer**.
- A Behringer WING console reachable from Home Assistant on the local network.
- OSC remote control enabled on the console. This integration uses UDP port `2223`.

## Installation

### Marketplace (recommended, Home Assistant 2026.11+)

The [Marketplace](https://www.home-assistant.io/integrations/marketplace/) is built into Home Assistant 2026.11 and newer.

[![Open in Marketplace](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=speedy3wk&repository=ha-wing-limiter&category=integration)

1. Open **Settings → Marketplace** as an administrator and accept the community-content warning if prompted.
2. Select **Add from link**, enter `https://github.com/speedy3wk/ha-wing-limiter` and select **Add**. Connect GitHub if prompted. If asked for a content type, select **Integration**.
3. Open **Wing Limiter** and select **Install**.
4. Follow the integration setup flow. If it does not open, add **Wing Limiter** under **Settings → Devices & services → Add integration**. Restart only if the Marketplace requests it.

Integration updates still require a Home Assistant restart.

On older supported Home Assistant versions, add this repository to HACS as an **Integration**, install it and restart before adding the integration.
Existing HACS installations migrate automatically to the Marketplace when updating to Home Assistant 2026.11.

### Manual

Copy `custom_components/wing_limiter` into your Home Assistant `config/custom_components/` directory, restart Home Assistant, then add **Wing Limiter** under **Settings → Devices & services**.

## Configuration

Add **Wing Limiter** and enter:

- **WING IP address** — the console's IP address.
- **Polling interval** — how often to poll the console, from 1 to 60 seconds (default: 5).

Use **Configure** to change the polling interval or enable metering. Use **Reconfigure** to change the console address without recreating the integration or its entities.

Controls use UDP port `2223`. Metering additionally needs TCP port `2222` and UDP replies to a dynamically assigned port on Home Assistant. IPv4 addresses and IPv4-resolvable hostnames are supported.

## Entities

Each of the four main buses gets a **Dynamics model** sensor and a **Compressor** enable switch. For `COMP`, the following additional controls are available:

| Control | Range / choices |
|---|---|
| Threshold | -60 to 0 dB, 0.5 dB steps |
| Make-up gain | -6 to 12 dB, 0.5 dB steps |
| Dry/wet mix | 0–100% |
| Ratio | WING's discrete ratios, 1.1:1 to 100:1 |
| Attack / hold / release | 0–120 / 1–200 / 4–4000 ms |
| Knee | 0–5 |
| Detector / envelope | PEAK or RMS / LIN or LOG |
| Automatic timing | On/off |
| Sidechain | Filter type, frequency, Q, source and tap |

Other Dynamics models are detected and displayed, but their model-specific controls are unavailable rather than using incorrect ranges. Select `COMP` on the console if you want to use these controls. Logarithmic controls (release, filter frequency and Q) are quantized by the console; the integration displays the actual read-back value.

Commands are not shown optimistically: the next read-back determines the displayed state. A successful UDP send alone does not confirm that the console applied it.

### Optional metering

Enable metering in the integration's options to add input left/right and output left/right sensors, plus a gain reduction sensor per main. HA samples the latest meter report approximately once per second; this is not a real-time audio analyzer. Levels are in dB relative to digital full scale. Gain reduction scaling is supported **only for `COMP`**.

Metering uses one native TCP subscription, renewed every four seconds, and a UDP receiver. It does not take over the console's OSC subscription. Missing or malformed meter data makes the meter sensors unavailable without disabling the controls. Connections close when the entry unloads. Consider excluding meter sensors from Recorder if you do not need their history.

### User profiles

Profiles are stored locally in Home Assistant, persist across restarts, and belong to one integration entry and main bus. The actions are:

- `wing_limiter.save_profile`: capture fresh `COMP` and sidechain settings.
- `wing_limiter.restore_profile`: restore a profile to its original main and verify read-back.
- `wing_limiter.delete_profile`: delete a profile.
- `wing_limiter.list_profiles`: return names, main bus numbers and models.

Save/restore/delete take `entry_id`, `main_index` (1–4), and `name`. Save also accepts `overwrite: true`; existing names are protected by default. List only takes `entry_id` and requires a response variable in automations.

```yaml
action: wing_limiter.save_profile
data:
  entry_id: YOUR_CONFIG_ENTRY_ID
  main_index: 1
  name: Live
```

```yaml
action: wing_limiter.list_profiles
data:
  entry_id: YOUR_CONFIG_ENTRY_ID
response_variable: saved_profiles
```

**Restoring also restores compressor on/off.** The console must already use `COMP`. Writes are not atomic: if transmission or verification fails, some settings may already have changed, and the action reports an error instead of claiming success. Do not edit the same settings on the console while capturing/restoring a profile. Removing the integration entry deletes its profiles.

## Troubleshooting

- Confirm that Home Assistant and the console can communicate over the local network.
- Check that OSC remote control is enabled on the console and that UDP port `2223` is reachable.
- If setup fails, verify the IP address and try again while the console is powered on.
- A normal poll has two bounded OSC batches, each with a 1.5-second response deadline, rather than a separate timeout for every parameter.
- Unsupported model controls are unavailable by design, not an indication of a network failure.
- If only meters fail, check TCP `2222` and the return UDP path.

## Development

The validation workflow runs `hassfest` and repository metadata checks. Tests cover OSC UDP framing, model gating, entity identity, reconfiguration, persistent profiles and native TCP/UDP metering using a simulated console. CI runs against pinned stable HA 2026.10.4, beta 2026.11.0b2 and the moving `dev` branch, including a weekly scheduled run. Development/beta checks detect upcoming changes; they do not guarantee compatibility with unreleased versions.

```sh
python3.14 -m venv .venv
source .venv/bin/activate
pip install -r requirements_test.txt
ruff check custom_components tests
ruff format --check custom_components tests
pyright --pythonpath "$(command -v python)"
python -m pytest -q
```

The new v0.2 controls and meter protocol are covered by simulated-console tests, **not certified against physical WING hardware**. Protocol ranges and meter framing follow [Patrick-Gilles Maillot's WING remote protocol reference](https://sites.google.com/site/patrickmaillot/wing). This integration controls the WING's Dynamics settings; it does not implement its own audio limiter.

## License

This project is distributed under the MIT License. See [LICENSE](./LICENSE).
