"""Lighting-only protocol for MDA's verified 0x00AD Bluetooth controller.

Wire-format references: 8none1/lednetwf_ble protocol_docs and live MDA tests.
No firmware, reset, wiring, LED-count, or persistent hardware-setting commands.
"""

import math
from dataclasses import dataclass

WRITE_UUID = "0000ff01-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000ff02-0000-1000-8000-00805f9b34fb"
SERVICE_DATA_UUID = "00005a00-0000-1000-8000-00805f9b34fb"
PRODUCT_ID = 0x00AD

# Three palettes from the published LEDnetWF IOTBT scene captures (issue #83).
# Fields are scene ID, mode, direction, and packed hue/saturation/value triples.
SCENES = {
    "Game": (
        1,
        0,
        1,
        ((0x58, 0xDE, 0x61), (0x3C, 0x64, 0x64), (0x68, 0xE4, 0x64), (0x96, 0x64, 0x64)),
    ),
    "Party": (
        3,
        0,
        1,
        (
            (0x0C, 0x64, 0x64),
            (0x1E, 0x64, 0x64),
            (0x5A, 0x64, 0x64),
            (0x6C, 0xE4, 0x64),
            (0x96, 0x64, 0x64),
        ),
    ),
    "Northern Lights": (2, 0, 1, ((0x70, 0xE4, 0x64), (0x5F, 0xE4, 0x64), (0x47, 0xE4, 0x64))),
}


def bounded(value: int, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"Expected integer in {minimum}..{maximum}")
    return value


def checksum(data: bytes) -> bytes:
    return data + bytes([sum(data) & 255])


def power(on: bool) -> bytes:
    if not isinstance(on, bool):
        raise ValueError("Power must be boolean")
    return checksum(bytes([0x3B, 0x23 if on else 0x24]) + bytes(10))


def color(hue: float, saturation: float, brightness: int) -> bytes:
    if not math.isfinite(hue) or not 0 <= hue <= 360:
        raise ValueError("Hue must be in 0..360")
    if not math.isfinite(saturation) or not 0 <= saturation <= 100:
        raise ValueError("Saturation must be in 0..100")
    packed = (round(hue) << 7) | round(saturation)
    value = bounded(brightness, 1, 100)
    return checksum(bytes([0x3B, 0xA1, packed >> 8, packed & 255, value]) + bytes(7))


def brightness(percent: int) -> bytes:
    value = bounded(percent, 1, 100)
    return checksum(bytes([0x3B, 1, 0, 0, value, 0, value]) + bytes(5))


def scene(name: str, speed: int = 50) -> bytes:
    scene_id, mode, direction, palette = SCENES[name]
    speed = bounded(speed, 1, 100)
    data = bytes(
        [0xE1, 1, 0, 100, scene_id, mode, direction, 100, speed, 0, 0xA1, 0, 0, 0, len(palette)]
    )
    return data + b"".join(bytes([0xA1, *entry]) for entry in palette)


def query() -> bytes:
    return bytes.fromhex("ea818a8b")


def validate_payload(payload: bytes) -> None:
    """Refuse everything except known status and ordinary lighting operations."""
    if payload == query():
        return
    if len(payload) == 13 and payload[0] == 0x3B and payload[-1] == sum(payload[:-1]) & 255:
        if payload[1] in (0x23, 0x24) and payload[2:12] == bytes(10):
            return
        if payload[1] == 0xA1 and payload[5:12] == bytes(7):
            packed = int.from_bytes(payload[2:4], "big")
            if packed >> 7 <= 360 and packed & 127 <= 100 and 1 <= payload[4] <= 100:
                return
        if payload[1] == 1 and payload[2:4] == bytes(2) and payload[5] == 0:
            if payload[4] == payload[6] and 1 <= payload[4] <= 100 and payload[7:12] == bytes(5):
                return
    if len(payload) >= 15 and 1 <= payload[8] <= 100:
        if any(payload == scene(name, payload[8]) for name in SCENES):
            return
    raise ValueError("Unsupported payload: only status and known lighting commands are allowed")


def frame(payload: bytes, sequence: int) -> bytes:
    validate_payload(payload)
    bounded(sequence, 0, 255)
    n = len(payload)
    return bytes([0, sequence, 128, 0, 0, n, n + 1, 10 if payload == query() else 11]) + payload


@dataclass(frozen=True)
class State:
    on: bool
    mode: int
    mode_id: int
    speed: int


def parse_notification(packet: bytes) -> State | None:
    # Only the complete single-frame EA81 status format observed on this rug.
    if len(packet) < 8 or packet[2:4] != b"\x80\x00":
        return None
    n = int.from_bytes(packet[4:6], "big")
    if len(packet) != 8 + n or packet[6] != n + 1 or packet[7] not in (0x15, 0x16):
        return None
    raw = packet[8:]
    if len(raw) != 27 or raw[:2] != b"\xea\x81" or int.from_bytes(raw[3:5], "big") != PRODUCT_ID:
        return None
    if raw[6] not in (0x23, 0x24):
        return None
    return State(raw[6] == 0x23, raw[7], raw[8], raw[9])


def matches(service_data: dict[str, bytes], address: str) -> bool:
    data = service_data.get(SERVICE_DATA_UUID, b"")
    return (
        len(data) == 14
        and data[0] == 0x80
        and data[1] == 7
        and data[2:8].hex() == address.replace(":", "").lower()
        and int.from_bytes(data[8:10], "big") == PRODUCT_ID
        and data[13] & 8 != 0
    )
