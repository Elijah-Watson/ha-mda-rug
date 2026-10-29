# Repository and installation conventions

Reviewed on October 29, 2026:

| Project | Relevant conventions adopted here |
| --- | --- |
| [Sonoff LAN](https://github.com/AlexxIT/SonoffLAN) | One integration under `custom_components/`, repository documentation/issues links, code owner, versioned manifest, simple `hacs.json` with a minimum HA version |
| [Pirate Weather](https://github.com/Pirate-Weather/pirate-weather-ha) | HACS-managed installation and updates, configuration through the HA UI, documented minimum HA version |
| [LEDnetWF BLE](https://github.com/8none1/lednetwf_ble) | Bluetooth dependency, local push classification, BLE discovery, related controller protocol |

MDA Rug follows the [HACS integration requirements](https://www.hacs.xyz/docs/publish/integration/):
one component directory, complete manifest, README, HACS metadata, and tagged releases.
HACS installs the component from the release tag; the separate release ZIP is for manual installation.
The icon is shipped locally using HA's [custom integration brand directory](https://contributors.home-assistant.io/core/integrations/brands/).

The repository includes a license, upstream attribution, protocol/transport tests,
Ruff checks, Home Assistant's hassfest validator, and HACS validation in GitHub Actions.
Raw BLE captures, personal device addresses, caches, and downloaded app files are excluded.

Unlike a larger general-purpose lighting integration, this integration deliberately
supports one verified controller profile and a small set of lighting commands.
