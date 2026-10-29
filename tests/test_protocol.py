import json
from pathlib import Path

import pytest

CAPTURED_GAME = bytes.fromhex(
    "04218000001b1c15ea810100ad0a2325011ef058df610000010064ffffffff02000000"
)


def test_actual_status_capture(protocol):
    state = protocol.parse_notification(CAPTURED_GAME)
    assert (state.on, state.mode, state.mode_id, state.speed) == (True, 0x25, 1, 30)


def test_actual_power_packet(protocol):
    assert (
        protocol.frame(protocol.power(True), 2).hex()
        == "00028000000d0e0b3b23000000000000000000005e"
    )


def test_actual_scene_packet(protocol):
    assert (
        protocol.frame(protocol.scene("Game", 30), 6).hex()
        == "00068000001f200be1010064010001641e00a100000004a158de61a13c6464a168e464a1966464"
    )


@pytest.mark.parametrize(
    "change",
    ["truncated", "wrong_product", "wrong_size", "fragment", "unknown_power", "unknown_opcode"],
)
def test_rejects_bad_or_unrelated_status(protocol, change):
    data = bytearray(CAPTURED_GAME)
    if change == "truncated":
        data.pop()
    elif change == "wrong_product":
        data[12] = 0xAE
    elif change == "wrong_size":
        data[5] -= 1
    elif change == "fragment":
        data[2] = 0
    elif change == "unknown_power":
        data[14] = 0xFF
    else:
        data[7] = 8
    assert protocol.parse_notification(bytes(data)) is None


@pytest.mark.parametrize(
    "payload",
    [
        "2222",
        "6212345678",
        "e014010000640100",
        "42071e1980",
        "ffffffff",
        "3b230000000000000000000000",
    ],
)
def test_configuration_firmware_and_unknown_commands_are_rejected(protocol, payload):
    with pytest.raises(ValueError):
        protocol.frame(bytes.fromhex(payload), 0)


@pytest.mark.parametrize("value", [-1, 0, 101, 255, True, 1.2])
def test_brightness_bounds(protocol, value):
    with pytest.raises(ValueError):
        protocol.brightness(value)


def test_odd_hue_preserves_low_bit(protocol):
    payload = protocol.color(121, 50, 25)
    packed = int.from_bytes(payload[2:4], "big")
    assert packed >> 7 == 121
    assert packed & 127 == 50


def test_discovery_checks_product_mac_and_profile(protocol):
    data = bytes.fromhex("8007aabbccddeeff00ad220a010d")
    assert protocol.matches({protocol.SERVICE_DATA_UUID: data}, "AA:BB:CC:DD:EE:FF")
    assert not protocol.matches({protocol.SERVICE_DATA_UUID: data}, "AA:BB:CC:DD:EE:FE")
    wrong = data[:8] + b"\x00\xae" + data[10:]
    assert not protocol.matches({protocol.SERVICE_DATA_UUID: wrong}, "AA:BB:CC:DD:EE:FF")


def test_all_supported_lighting_commands_pass_allowlist(protocol):
    payloads = [
        protocol.query(),
        protocol.power(True),
        protocol.power(False),
        protocol.color(359, 67, 1),
        protocol.brightness(100),
    ]
    payloads += [protocol.scene(name, 100) for name in protocol.SCENES]
    for payload in payloads:
        assert protocol.frame(payload, 255)[8:] == payload


def test_manifest_and_translations():
    root = Path(__file__).resolve().parents[1] / "custom_components/mda_rug"
    manifest = json.loads((root / "manifest.json").read_text())
    strings = json.loads((root / "strings.json").read_text())
    assert manifest["config_flow"] and manifest["dependencies"] == ["bluetooth"]
    assert strings == json.loads((root / "translations/en.json").read_text())
