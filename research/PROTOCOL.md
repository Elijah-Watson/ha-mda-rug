# Investigation record — 2026-10-29

## Findings

The official [Google Play listing](https://play.google.com/store/apps/details?id=com.mda.blev2)
links to [MDA's policy on magichue.net](https://faqsys.magichue.net/MDA/privacy/policy).
This was the first indication of a shared platform. Live advertisements and matching
control/status packets subsequently supported reuse of the LEDnetWF/Zengge protocol.
The underlying radio silicon/chip manufacturer has **not** been identified.

Searches for MDA rug repositories and the exact Android package found no MDA-specific
integration. [LEDnetWF BLE](https://github.com/8none1/lednetwf_ble) is a closely related
existing integration, not proof that every MDA feature works without changes.

Observed advertisement format (MAC address anonymized):

```
Name: IOTBTxxx
MAC: AA:BB:CC:DD:EE:FF
Service data UUID: 00005a00-0000-1000-8000-00805f9b34fb
Service data: 8007aabbccddeeff00ad220a010d
Manufacturer ID: 0x5A00
Initial manufacturer data:
8023250746f00064640000010064ffffffff020000000000000000
```

The 14-byte service data carries the MAC, product 0x00AD, firmware byte 0x22,
LED version 0x0A, and flags2 0x0D. These agree with the app's firmware display.
The upstream device table calls product 173 (0xAD) a Symphony curtain controller.
That is a controller-family label, not a claim that this product is a curtain.

Observed GATT:

| Service | Characteristic | Properties | Handling |
| --- | --- | --- | --- |
| FFFF | FF01 | write, write without response | Lighting only |
| FFFF | FF02 | notify | Status |
| FE00 | FF11 | write, write without response | Not used |
| FE00 | FF22 | notify | Not used |

## Confirmed packets

An eight-byte transport envelope precedes the payload:
`00 SEQ 80 00 LEN_HI LEN_LO LEN_PLUS_1 CMD_ID`.
CMD_ID is 0x0A for the tested query and 0x0B for lighting commands.
Replies use 0x15 for queries and 0x16 for unsolicited updates.

Power on (sequence 2):

```
00028000000d0e0b3b23000000000000000000005e
```

Power off uses 0x24 instead of 0x23 and checksum 0x5F.

Query:

```
000180000004050aea818a8b
```

Game scene at speed 30:

```
00068000001f200be1010064010001641e00a100000004a158de61a13c6464a168e464a1966464
```

Corresponding query reply:

```
04218000001b1c15ea810100ad0a2325011ef058df610000010064ffffffff02000000
```

Inside the 27-byte EA81 reply: product at bytes 3–4, power at byte 6,
mode at byte 7, mode/scene ID at byte 8, speed at byte 9.
Game, Party, and Northern Lights reported IDs 1, 3, and 2 respectively,
with the requested speed 30. Power transitions were confirmed in both directions.

## Unverified or rejected paths

- Standard `3B A1` HSV commands cause the rug to report mode ID 110, consistent with
  selecting a solid mode, but the reported color fields did not track the requested HSV.
  The user did not watch that test and chose to defer visual checks.
- Standard `3B 01` brightness writes were accepted and produced notifications, but
  did not yield a clearly changed brightness field. They are not considered verified.
- Old `42 effect speed brightness checksum` commands did not change the mode.
  They were removed from the implementation.
- A read-only `63 12 21 F0 86` LED settings query produced no response. No settings
  were written. This query is not part of the delivered integration.
- The first test attempted to restore effect 7 with the old 0x42 command, but it was
  ignored. No claim of exact scene restoration is made. Testing ended with power off
  and Northern Lights selected at speed 30.
- Only small, single-frame status replies are parsed. Unknown formats are ignored.
- No firmware, reset, or hardware-configuration writes were sent.

Local raw scans and test records are in `captures/` (excluded from the release ZIP and Git).
They contain nearby device identifiers; the deliverable does not include the full scans.

## Sources and next investigation route

- [LEDnetWF transport notes](https://github.com/8none1/lednetwf_ble/blob/main/protocol_docs/04_connection_transport.md)
- [LEDnetWF protocol implementation](https://github.com/8none1/lednetwf_ble/blob/main/custom_components/lednetwf_ble/protocol.py)
- [Controller capability data](https://github.com/8none1/lednetwf_ble/blob/main/custom_components/lednetwf_ble/data/ble_devices.json)
- [Scene capture issue #83](https://github.com/8none1/lednetwf_ble/issues/83)
- [HA Bluetooth developer documentation](https://contributors.home-assistant.io/core/integrations/bluetooth/)
- [HA 2026.10.4 Bluetooth dependencies](https://github.com/home-assistant/core/blob/2026.10.4/homeassistant/components/bluetooth/manifest.json)
- [Bleak write size/MTU documentation](https://bleak.readthedocs.io/en/latest/api/index.html)

If the visual color/dimming test fails, the most direct next input is the installed
`com.mda.blev2` APK and a short Android HCI capture of one action at a time. ADB can
list this app's APK paths with `adb -s PHONE_SERIAL shell pm path com.mda.blev2`, then
pull each listed APK. Static inspection can identify color encoders, scene tables,
and transport variants without needing an emulator to control the rug.

For traffic capture, Android documents enabling Developer Options → Bluetooth HCI
snoop log, restarting Bluetooth, reproducing commands, and extracting a bug report.
Do not assume `adb pull /data/misc/bluetooth/logs` works on an unrooted Samsung.
Prefer finding the raw snoop log within `adb -s PHONE_SERIAL bugreport capture.zip`.
A full bug report can contain unrelated personal information, so process locally and
share only the necessary Bluetooth capture. [Android guidance](https://source.android.com/docs/core/connect/bluetooth/verifying_debugging).

Emulation remains possible: Android now supports virtual BLE, and
[Bumble documents bridging an emulator to a physical controller](https://google.github.io/bumble/platforms/android.html).
That needs additional radio bridging setup; an emulator's virtual BLE support alone
is not automatic passthrough to the Windows Intel radio. Direct PC BLE testing avoided
that setup here. Phone APK extraction was not required.
