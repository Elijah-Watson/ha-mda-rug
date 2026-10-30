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
   Regression tests preserve those three external fixtures. Scene names describe
   the source app's palettes; exact MDA app naming and animation equivalence are
   still unverified. The additional 43 scenes have not been enabled without rug tests.
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
