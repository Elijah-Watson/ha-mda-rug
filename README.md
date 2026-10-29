# MDA Rug — Home Assistant Bluetooth integration

A small local integration for the MDA Rugs LED rug tested on October 29, 2026.
It creates one light entity and uses Home Assistant's existing Bluetooth integration.
No cloud account, MQTT broker, emulator, or running phone app is required.

**Version 0.1.0: power and three scenes are confirmed by real rug status replies.
Color and dimming are experimental and still need visual testing.**
The Home Assistant wrapper has not yet been installed or tested inside HA.

## Supported controller

- MDA app Android package: `com.mda.blev2`
- Advertisement name pattern: `IOTBT*`
- Controller product: `0x00AD`; BLE protocol 7; hardware/LED version 10
- App-reported firmware: `80.00AD.22.0D,V10`
- GATT lighting write: `0000ff01-0000-1000-8000-00805f9b34fb`
- GATT notifications: `0000ff02-0000-1000-8000-00805f9b34fb`

Other MDA controller revisions are deliberately not accepted automatically.
The same hardware may appear in other brands; discovery asks you to confirm the device.

## Features and verification

| Feature | Status |
| --- | --- |
| On/off | Confirmed through status replies on the physical rug |
| Game, Party, Northern Lights | Scene IDs and speed confirmed through status replies |
| Effect speed | Encoded in the tested scene format; configurable from 1–100 |
| Solid HS color | Enters solid mode in status; actual color still needs visual testing |
| Brightness | BLE writes accepted, but brightness is not confirmed by status; needs visual testing |
| Power changes made with the app | Advertisement parser included; HA callback path not tested live |
| HA installation, discovery, restore, proxies | Implemented; runtime validation pending |

Scene names and palettes come from published Magic Hue/Zengge interoperability captures;
they have not been matched against every scene name in MDA's app. This is a three-scene
starter integration, not a complete reproduction of every MDA mode.

Color, brightness, and the last requested scene label are treated as assumed state.
The light does not claim to read back its exact color or brightness. If an external controller
changes the mode ID, the old requested values are cleared where detectable. Different
palettes can share a scene ID, so an external palette change may not be distinguishable.

## Installation with HACS

Requires Home Assistant 2026.10 or newer and a connectable Bluetooth adapter or proxy.

1. In **HACS → ⋮ → Custom repositories**, add
   `https://github.com/Elijah-Watson/ha-mda-rug` with type **Integration**.
2. Find **MDA Rug** in HACS and download the latest release.
3. Restart Home Assistant.
4. Open **Settings → Devices & services → Add integration → MDA Rug**.
5. Enter your rug's MAC address from the MDA app.
6. Setup validates the advertisement and reads the rug's status. If no connectable
   adapter sees the rug, the entry remains saved and retries automatically.
7. Fully close the MDA phone app if connections fail.

HACS manages future updates. After downloading an update, restart Home Assistant.
For a manual installation, copy `custom_components/mda_rug` from this repository
or the release ZIP into `/config/custom_components/`, then follow steps 3–7.
To remove it, delete the integration entry in Settings, remove its HACS download,
and restart Home Assistant.

Automatic Bluetooth discovery is also supported. Options for the integration let you
change the speed used the next time you select a scene.

The integration relies on HA's shared scanner and nearest connectable device lookup.
It connects for an action, subscribes, verifies identity/state, sends commands, reads status,
and disconnects. It does not create a second scanner or continuously poll the rug.

The adapter/proxy must support writes of at least **43 bytes** for all included scenes
(ATT MTU at least 46). The tested Windows connection negotiated MTU 512. A smaller MTU
produces a clear error before lighting commands are sent; unverified packet fragmentation
is not attempted. This still needs validation with your eventual HA adapter.

## Use

Use the normal light card for power, color, brightness, and effect selection.
An automation can select a scene:

```yaml
action: light.turn_on
target:
  entity_id: light.mda_rug  # Replace with the entity ID assigned by your HA instance.
data:
  effect: Northern Lights
```

For the first visual test, try red at 30%, blue at 20%, then a scene. If color or brightness
is wrong, record the exact action and visible result. Those two features are experimental;
we can capture the corresponding MDA app commands to resolve differences.

## Restricted command surface

All integration writes go to the lighting characteristic FF01. The transport validates
the entire command batch before connecting. Only these payloads are accepted:

- Status query `EA 81 8A 8B`.
- Precisely structured `3B` power, solid-color, and brightness commands.
- Exact `E1 01` scene templates with a bounded speed.

There is no firmware updater, reset, pairing-key change, raw-command service, wiring setup,
LED-count change, or hardware-configuration control. No writes are made to the separate
FE00/FF11 service. These restrictions reduce risk; they cannot guarantee the absence of
bugs in a third-party controller's firmware.

## Development

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check custom_components tools tests
```

The test suite exercises real capture fixtures and a simulated BLE transport. It does
not pretend to be a Home Assistant runtime test. No test in `tests/` accesses hardware.

Read-only discovery and GATT inspection:

```powershell
.\.venv\Scripts\python.exe tools\ble_probe.py --address AA:BB:CC:DD:EE:FF
```

`tools/rug_control.py --address YOUR_RUG_MAC status` queries the rug. Its explicitly selected `color-test` and
`scenes-test` actions change lights and finish by switching them off; they do not restore
the previous scene. Use those only when you are ready to observe the rug.

See [research/PROTOCOL.md](research/PROTOCOL.md) for findings, exact packets, and sources.
