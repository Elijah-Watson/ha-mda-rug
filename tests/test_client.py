import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

STATE = bytes.fromhex("04218000001b1c15ea810100ad0a2325011ef058df610000010064ffffffff02000000")


class FakeBle:
    def __init__(self, limit=509):
        self.characteristic = SimpleNamespace(max_write_without_response_size=limit)
        self.services = SimpleNamespace(get_characteristic=lambda _: self.characteristic)
        self.disconnect = AsyncMock()
        self.state = bytearray(STATE)
        self.writes = []
        self.ignore_controls = False

    async def start_notify(self, uuid, callback):
        assert uuid == "0000ff02-0000-1000-8000-00805f9b34fb"
        self.callback = callback

    async def write_gatt_char(self, characteristic, packet, response):
        assert characteristic is self.characteristic
        assert response is False
        self.writes.append(bytes(packet))
        payload = packet[8:]
        if payload == bytes.fromhex("ea818a8b"):
            self.callback(None, self.state)
        elif not self.ignore_controls:
            if payload[:2] in (b"\x3b\x23", b"\x3b\x24"):
                self.state[14] = payload[1]
            elif payload[:2] == b"\xe1\x01":
                self.state[15:18] = bytes([0x25, payload[4], payload[8]])
            elif payload[:2] == b"\x3b\xa1":
                self.state[15:17] = bytes([0x25, 110])


@pytest.fixture
def connected(monkeypatch, client_module_fixture):
    fake = FakeBle()
    connect = AsyncMock(return_value=fake)
    monkeypatch.setattr(client_module_fixture, "establish_connection", connect)
    return fake, connect, client_module_fixture.RugClient(lambda: object(), "Test rug")


async def test_queries_before_mutating_and_disconnects(connected, protocol):
    fake, _, client = connected
    result = await client.execute([protocol.power(False)])
    assert not result.on
    assert fake.writes[0][8:] == protocol.query()
    assert fake.writes[-1][8:] == protocol.query()
    fake.disconnect.assert_awaited_once()


async def test_rejects_entire_unsafe_batch_before_connecting(connected, protocol):
    fake, connect, client = connected
    with pytest.raises(ValueError):
        await client.execute([protocol.power(True), bytes.fromhex("2222")])
    connect.assert_not_awaited()
    assert fake.writes == []


async def test_small_mtu_rejects_batch_before_controls(connected, protocol, client_module_fixture):
    fake, _, client = connected
    fake.characteristic.max_write_without_response_size = 20
    with pytest.raises(client_module_fixture.RugError, match="MTU"):
        await client.execute([protocol.power(True), protocol.scene("Party")])
    assert len(fake.writes) == 1  # Identity/status query only.
    fake.disconnect.assert_awaited_once()


async def test_ignored_power_command_is_failure(connected, protocol, client_module_fixture):
    fake, _, client = connected
    fake.ignore_controls = True
    with pytest.raises(client_module_fixture.RugError, match="power state"):
        await client.execute([protocol.power(False)])
    fake.disconnect.assert_awaited_once()


async def test_scene_confirmation(connected, protocol):
    _, _, client = connected
    state = await client.execute([protocol.scene("Party", 75)])
    assert (state.mode_id, state.speed) == (3, 75)


async def test_ignored_scene_is_failure(connected, protocol, client_module_fixture):
    fake, _, client = connected
    fake.ignore_controls = True
    with pytest.raises(client_module_fixture.RugError, match="scene"):
        await client.execute([protocol.scene("Party")])


async def test_ignored_solid_color_is_failure(connected, protocol, client_module_fixture):
    fake, _, client = connected
    fake.ignore_controls = True
    with pytest.raises(client_module_fixture.RugError, match="solid-color mode"):
        await client.execute([protocol.color(0, 100, 30, "BGR")])


async def test_solid_color_mode_is_confirmed(connected, protocol):
    _, _, client = connected
    state = await client.execute([protocol.color(0, 100, 30, "BGR")])
    assert state.mode_id == 110


async def test_write_error_disconnects(connected, monkeypatch, client_module_fixture):
    fake, _, client = connected
    monkeypatch.setattr(fake, "write_gatt_char", AsyncMock(side_effect=OSError("lost connection")))
    with pytest.raises(OSError):
        await client.execute()
    fake.disconnect.assert_awaited_once()


async def test_cancelled_query_disconnects(connected, monkeypatch):
    fake, _, client = connected
    monkeypatch.setattr(fake, "write_gatt_char", AsyncMock(side_effect=asyncio.CancelledError))
    with pytest.raises(asyncio.CancelledError):
        await client.execute()
    fake.disconnect.assert_awaited_once()


async def test_close_prevents_new_connections(connected, client_module_fixture):
    _, connect, client = connected
    await client.close()
    with pytest.raises(client_module_fixture.RugError, match="unloading"):
        await client.execute()
    connect.assert_not_awaited()


async def test_missing_adapter_does_not_connect(monkeypatch, client_module_fixture):
    connect = AsyncMock()
    monkeypatch.setattr(client_module_fixture, "establish_connection", connect)
    client = client_module_fixture.RugClient(lambda: None, "Test")
    with pytest.raises(client_module_fixture.RugError, match="adapter"):
        await client.execute()
    connect.assert_not_awaited()
