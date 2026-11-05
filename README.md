# MDA Rug — Home Assistant Bluetooth integration

A small local integration for the MDA Rugs LED rug tested on October 29, 2026.
It creates a light and an Effect speed setting, and uses Home Assistant's existing Bluetooth
integration. No cloud account, MQTT broker, emulator, or running phone app is required.

**Version 0.2.0: power and corrected solid colors are visually verified on the tested rug.
Solid-color dimming works by resending the color with its brightness.**
Scene names are provisional palettes and do not claim to match the MDA app exactly.

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
| On/off | Visually confirmed and verified through physical rug status replies |
| All 46 captured scenes | Accepted through status replies and watched on the rug: each animates; names and looks not compared with MDA's app |
| Effect speed | A number entity from 1–100, shared by all scenes and applied at once to a running scene; slow and fast visually confirmed |
| Solid HS color | Primaries, white, an intermediate hue and a partial saturation visually confirmed; BGR correction swaps red/blue in software |
| Brightness | Solid red visually confirmed in steps from 100% down to 1%; standalone dimming command is ignored |
| Scene brightness | Northern Lights at 10%, 70% and 100% visually confirmed; other scenes use the same scaling |
| Power changes made with the app | Advertisement parser included; HA callback path not tested live |
| HA installation and manual setup | HACS installation and config flow verified on HA 2026.10.4; entry retries while no adapter sees the rug |
| Light entity through an ESPHome Bluetooth proxy | Verified end to end on HA 2026.10.4, including 55-byte scene writes |
| HA discovery, restore | Requires end-to-end validation |

Scene names and palettes come from published Magic Hue/Zengge interoperability captures;
they have not been matched against every scene name in MDA's app. All 46 scenes in that
capture are included. The capture came from a different lamp in this controller family, so a
scene may not look exactly as it does in MDA's app. Music sync is not supported: no source
documents it.

Power is read from the rug. Color, brightness, and the last requested scene label are the
values last requested, because the rug does not report them.
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
change the software color correction (BGR by default, RGB if no correction is needed).

The integration relies on HA's shared scanner and nearest connectable device lookup.
It connects for an action, subscribes, verifies identity/state, sends commands, reads status,
and disconnects. It does not create a second scanner or continuously poll the rug.

The adapter/proxy must support writes of at least **55 bytes** for all included scenes
(ATT MTU at least 58). The tested Windows connection negotiated MTU 512. A smaller MTU
produces a clear error before lighting commands are sent; unverified packet fragmentation
is not attempted. An ESPHome Bluetooth proxy on an ESP32-C3 has been tested and handles all
scenes; other adapters have not.

## Use

Use the normal light card for power, color, brightness, and effect selection. The effect
`off` means a solid color. An automation can select a scene:

```yaml
action: light.turn_on
target:
  entity_id: light.mda_rug  # Replace with the entity ID assigned by your HA instance.
data:
  effect: Northern Lights
```

The tested controller displays raw red as blue and raw blue as red. BGR correction fixes
that in outgoing solid colors and scene palettes; it does not change wiring settings.
Brightness changes resend the selected color or palette. If HA does not know the current
selection (for example after app control or a restart while off), dimming starts from white.
Scene brightness and speed changes may restart the animation.

## Restricted command surface

All integration writes go to the lighting characteristic FF01. The transport validates
the entire command batch before connecting. Only these payloads are accepted:

- Status query `EA 81 8A 8B`.
- Precisely structured `3B` power and solid-color commands, with brightness inside the color command.
- Exact `E1 01` scene templates with bounded speed and palette intensity.

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
See [research/CALIBRATION.md](research/CALIBRATION.md) for the visual results,
closely matching firmware reference, and remaining uncertainties.
