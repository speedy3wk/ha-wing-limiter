# Wing Limiter

Control the compressors on the four main buses of a Behringer WING console from Home Assistant over OSC/UDP.

## Features

- One compressor switch and threshold control for each main bus (Main 1–4).
- Main bus names are used for the corresponding Home Assistant devices when available.
- Configure the console IP address and polling interval from the Home Assistant UI.

## Requirements

- A Behringer WING console reachable from Home Assistant on the local network.
- OSC remote control enabled on the console. This integration uses UDP port `2223`.

## Installation

### HACS

1. In HACS, open **Custom repositories**.
2. Add `https://github.com/speedy3wk/ha-wing-limiter` with category **Integration**.
3. Install **Wing Limiter** and restart Home Assistant.
4. Add the integration under **Settings → Devices & services → Add integration**.

### Manual

Copy `custom_components/wing_limiter` into your Home Assistant `config/custom_components/` directory, restart Home Assistant, then add **Wing Limiter** under **Settings → Devices & services**.

## Configuration

Add **Wing Limiter** and enter:

- **WING IP address** — the console's IP address.
- **Polling interval** — how often to poll the console, from 1 to 60 seconds (default: 5).

The integration communicates over UDP port `2223`.

## Entities

Each of the four main buses gets:

- **Compressor** — turns the bus compressor on or off.
- **Threshold** — sets the compressor threshold from -60 to 0 dB in 0.5 dB steps.

## Troubleshooting

- Confirm that Home Assistant and the console can communicate over the local network.
- Check that OSC remote control is enabled on the console and that UDP port `2223` is reachable.
- If setup fails, verify the IP address and try again while the console is powered on.

## Development

The GitHub Actions validation workflow runs Home Assistant's `hassfest` and HACS checks on pushes and pull requests.

## Migrating from the WING OSC integration

The integration domain changed from `wing_osc` to `wing_limiter`. Back up Home Assistant, remove the old integration entry, remove its `custom_components/wing_osc` directory, then install this integration and add **Wing Limiter**. Existing entities are not migrated automatically; entity IDs and device registry entries can change, so update automations, scripts, and dashboards as needed.

## License

This project is distributed under the MIT License. See [LICENSE](./LICENSE).
