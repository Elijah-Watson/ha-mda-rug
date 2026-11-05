# Calibration and protocol review — October 30, 2026

## Strongest references

1. [LEDnetWF issue #82](https://github.com/8none1/lednetwf_ble/issues/82) reports
   firmware `80.00AD.22.0D.V10`, product `0x00AD`, and **BGR** color order in the
   Zengge app. That is a much closer match than a generic IOTBT controller. It
   independently supports the red/blue swap measured on this rug. The issue's
   SM16703P is an LED driver identification for that other device; it does **not**
   establish the radio chip or LED driver in this rug.
2. [Issue #83's original Effects.txt](https://github.com/user-attachments/files/29386009/Effects.txt)
   contains app write packets for 46 named scenes. The uncorrected Game, Party,
   and Northern Lights encoders match its full packets exactly at speed 80.
   Regression tests preserve those three external fixtures. Its names turned out
   to be partly wrong; see the MDA app capture below.
3. The upstream [basic command reference](https://github.com/8none1/lednetwf_ble/blob/61da7f5a74943075dcd4940c287bd2bab36d1636/protocol_docs/05_basic_commands.md)
   describes `3B A1` with packed `(hue << 7) | saturation`, brightness at byte 4,
   and checksum. It warns that later fields can mean RGB on one device and timing
   on another. This integration retains zeros in those fields, as already tested.
4. The app-derived [device capability table](https://github.com/8none1/lednetwf_ble/blob/61da7f5a74943075dcd4940c287bd2bab36d1636/custom_components/lednetwf_ble/data/ble_devices.json)
   classifies product 173 as `curtainLightE2` / `wifibleSymphonyCurtainLight` and
   lists multiple generations of color and power commands. This is a controller
   family classification, not evidence that an MDA rug is a curtain or that every
   listed operation works on its firmware.

The reviewed upstream revision was `61da7f5a74943075dcd4940c287bd2bab36d1636`.
No authoritative MDA-specific BLE command specification or radio-chip
identification was found. The closest sources remain app-derived code and
captures, checked against this rug's own behavior.

## Measured mapping and implementation

| Operation | Observation | Integration behavior |
| --- | --- | --- |
| Power | On/off visually confirmed | Retain `3B 23` / `3B 24` |
| Raw hue 0 / 120 / 240 | Blue / green / red | Default software BGR correction |
| Corrected red / blue | Correct uniform colors | `wire_hue = (240 - requested_hue) % 360` |
| Standalone `3B 01` dimming | No visible change | Removed from the production command allowlist |
| Corrected red, value 10 then 70 | Dimmer then clearly brighter, still red | Resend `3B A1` color with requested brightness |
| Corrected Northern Lights at 10% | Blue and green, dim | Scale intensity in each palette entry |
| Corrected Northern Lights at 70% | Command sent; no visual response collected | Remains unverified |

BGR correction swaps red and blue in software; it is not a controller wiring
change. In HSV space this preserves saturation and brightness. Tests also compare
the hue transform with an independent RGB-channel-swap calculation across mixed
colors, but visual testing has covered only primary colors. White, partial
saturation, intermediate hues, and the full brightness range remain to be checked.

Scene dimming preserves the scene header and modifies only the value bytes in
the existing palette. This may restart an animation. It is less thoroughly
validated than solid-color dimming and is documented as provisional.

## Why the earlier assumptions failed

The IOTBT name does not identify a unique command set. The upstream project
distinguishes Telink `E2 0B`, segment `E1 03`, and another `E0 01` color variant.
Issue #82 recommends the segment path for a similar controller, but this rug
visibly responds to `3B A1`. That direct evidence takes precedence over trying
alternative formats based only on a family name.

The app's `bright_value_v2` template matches the standalone brightness packet we
sent. Its presence in a capability table is therefore insufficient evidence that
the rug implements it in the current mode. Resending the color is supported by
our visual test and avoids relying on the ignored command.

Status replies reliably establish power, mode ID, and scene speed. They have not
been validated as exact color/brightness readback. The integration continues to
report requested color and brightness as assumed state and does not reinterpret
unverified bytes as measured values. Cached selections are discarded when the
observed mode changes or when the software color correction changes.

## Best next evidence, when live testing resumes

- Compare the MDA app's solid primaries, an odd hue with partial saturation,
  and brightness 10/70 using Android HCI or app `HBConnectionImpl: writer.bytes`
  logs. The upstream [capture discussion](https://github.com/8none1/lednetwf_ble/issues/83#issuecomment-4797808654)
  confirms that the latter logs can expose actual outgoing commands.
- Compare the three scene names, palettes, speed, and brightness with MDA's UI.
- Check commands through the eventual HA Bluetooth adapter or active proxy.

No further live calibration was performed after the owner stepped away. No
firmware, reset, LED count, wiring, or persistent controller-setting writes are
part of this integration.

## Live validation — November 4, 2026

Version 0.2.0 on HA 2026.10.4, through an ESPHome Bluetooth proxy on an ESP32-C3 (Apollo MSR-2),
with a person watching the rug. This closes the open checks above.

| Check | Result |
| --- | --- |
| Red, green, blue, white, orange, pale pink (saturation 40), teal | All correct |
| Solid red at 100, 50, 25, 10, 5 and 1% | Each step visibly different |
| All 46 scenes, including modes 1 and 2 and direction 2 | Status replies matched; each animated |
| Scene writes of up to 55 bytes | Accepted through the proxy |
| Effect speed 10, 100 and 50 on Northern Lights | Speed visibly changed |
| Northern Lights at 10, 70 and 100% | Dimmed and recovered |

The status bytes were not checked as color or brightness readback.

## MDA app capture — November 4 and 5, 2026

All 46 scenes were selected in MDA's app, version 1.0.3, with each name read off the screen
and each write taken from the app's `HBConnectionImpl: writer.bytes` log. `tests/scene_capture.txt`
holds the result, in the app's order: Life 10, Scenery 14, Holidays 12, Moods 10.

- Every packet is byte-identical to the Zengge capture in issue #83, including speed.
- 34 names were right. The 12 Holidays names in that capture were rotated by six places:
  MDA's Christmas II (ID 102, red, white, green, white) was labelled Thanksgiving.
- Each scene has its own default speed: 40, 50, 60, 65 or 80. The app's slider follows it.
- Through this integration, solid red showed red and Iceland Blue showed blue and cyan, with a
  person watching. The Iceland Blue packet carried swapped hues (59, 34, 41), so the rug swaps
  red and blue in scenes as it does in solid colors, and the BGR correction is right for both.
- MDA's app sends scene palettes without that correction. How those look on the rug from the
  app, and how the app sends solid colors, were not checked.
