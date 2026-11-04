"""Small, serialized BLE client shared by Home Assistant and offline tests."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence

from bleak import BleakClient, BLEDevice
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from . import protocol


class RugError(Exception):
    """A command could not be delivered or verified."""


class RugClient:
    """Connect on demand, verify the controller, write, query, and disconnect."""

    def __init__(self, get_device: Callable[[], BLEDevice | None], name: str, speed: int = 50):
        self.get_device = get_device
        self.name = name
        self.speed = speed
        self.on_speed_change: Callable[[int], Awaitable[None]] | None = None
        self.state: protocol.State | None = None
        self._lock = asyncio.Lock()
        self._event = asyncio.Event()
        self._sequence = 0
        self._closed = False

    def _notify(self, _characteristic, data: bytearray) -> None:
        state = protocol.parse_notification(bytes(data))
        if state is not None:
            self.state = state
            if data[7] == 0x15:
                self._event.set()

    async def _write(self, client: BleakClient, payload: bytes) -> None:
        self._sequence = (self._sequence + 1) % 256
        packet = protocol.frame(payload, self._sequence)
        characteristic = client.services.get_characteristic(protocol.WRITE_UUID)
        if characteristic is None:
            raise RugError("The rug's lighting characteristic is missing")
        # No unverified fragmentation or writes to the separate firmware service.
        limit = characteristic.max_write_without_response_size
        if len(packet) > limit:
            raise RugError(
                f"Bluetooth adapter permits {limit}-byte writes; this command needs {len(packet)}. Use an adapter/proxy that negotiates a larger MTU."
            )
        await client.write_gatt_char(characteristic, packet, response=False)

    async def _query(self, client: BleakClient) -> protocol.State:
        self._event.clear()
        await self._write(client, protocol.query())
        try:
            await asyncio.wait_for(self._event.wait(), timeout=4)
        except TimeoutError as exc:
            raise RugError(
                "No valid MDA 0x00AD status reply; close the phone app and check Bluetooth range"
            ) from exc
        assert self.state is not None
        return self.state

    async def execute(self, payloads: Sequence[bytes] = ()) -> protocol.State:
        # Validate the ENTIRE transaction before connecting or sending anything.
        for payload in payloads:
            protocol.validate_payload(payload)
        async with self._lock:
            if self._closed:
                raise RugError("Integration is unloading")
            device = self.get_device()
            if device is None:
                raise RugError("No connectable Bluetooth adapter can currently reach the rug")
            client = await establish_connection(
                BleakClientWithServiceCache,
                device,
                self.name,
                max_attempts=3,
                ble_device_callback=self.get_device,
            )
            try:
                await client.start_notify(protocol.NOTIFY_UUID, self._notify)
                state = await self._query(client)
                if not payloads:
                    return state
                # Validate packet sizes for the whole batch before the first mutation.
                char = client.services.get_characteristic(protocol.WRITE_UUID)
                if char is None or any(
                    len(protocol.frame(p, 0)) > char.max_write_without_response_size
                    for p in payloads
                ):
                    raise RugError("Bluetooth MTU is too small for this lighting operation")
                for payload in payloads:
                    await self._write(client, payload)
                    await asyncio.sleep(0.15)
                state = await self._query(client)
                # Power and scene selection are confirmed by the device, not BLE write success.
                for payload in reversed(payloads):
                    if payload[:2] in (b"\x3b\x23", b"\x3b\x24"):
                        if state.on != (payload[1] == 0x23):
                            raise RugError("The rug did not report the requested power state")
                        break
                scene_payloads = [p for p in payloads if p[:2] == b"\xe1\x01"]
                if scene_payloads:
                    expected = scene_payloads[-1]
                    if (
                        state.mode != 0x25
                        or state.mode_id != expected[4]
                        or state.speed != expected[8]
                    ):
                        raise RugError("The rug did not report the requested scene and speed")
                if any(p[:2] == b"\x3b\xa1" for p in payloads):
                    if state.mode != 0x25 or state.mode_id != 110:
                        raise RugError("The rug did not report solid-color mode")
                return state
            finally:
                await client.disconnect()

    async def close(self) -> None:
        self._closed = True
        # Wait for any in-flight action's finally block to disconnect.
        async with self._lock:
            pass
