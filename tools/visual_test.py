"""Run a paced visual test through the integration's validated BLE client."""

import argparse
import asyncio
import importlib
import json
import sys
import types
from datetime import UTC, datetime
from pathlib import Path

from bleak import BleakScanner
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

package = types.ModuleType("rug_visual_test")
package.__path__ = [str(Path(__file__).resolve().parents[1] / "custom_components/mda_rug")]
sys.modules[package.__name__] = package
protocol = importlib.import_module("rug_visual_test.protocol")
RugClient = importlib.import_module("rug_visual_test.client").RugClient


async def main(args):
    device = await BleakScanner.find_device_by_address(args.address, timeout=20)
    if device is None:
        raise RuntimeError("Rug not advertising; fully close the MDA app and retry")
    client = RugClient(lambda: device, "MDA visual test")
    records = []
    phases = [
        ("OFF", [protocol.power(False)]),
        ("ON (previous scene)", [protocol.power(True)]),
        ("RED at 30%", [protocol.color(0, 100, 30, args.color_order)]),
        ("GREEN at 30%", [protocol.color(120, 100, 30, args.color_order)]),
        ("BLUE at 30%", [protocol.color(240, 100, 30, args.color_order)]),
        ("BLUE dimmed to 10%", [protocol.color(240, 100, 10, args.color_order)]),
        ("BLUE brightened to 70%", [protocol.color(240, 100, 70, args.color_order)]),
        *[(name, [protocol.scene(name, 30, args.color_order, 30)]) for name in protocol.SCENES],
    ]
    connection = await establish_connection(BleakClientWithServiceCache, device, "MDA visual test")
    try:
        await connection.start_notify(protocol.NOTIFY_UUID, client._notify)
        await client._query(connection)
        char = connection.services.get_characteristic(protocol.WRITE_UUID)
        for _, commands in phases:
            for payload in commands:
                protocol.validate_payload(payload)
                if len(protocol.frame(payload, 0)) > char.max_write_without_response_size:
                    raise RuntimeError("MTU is too small for the visual test")
        for label, commands in phases:
            for payload in commands:
                await client._write(connection, payload)
                await asyncio.sleep(0.15)
            state = await client._query(connection)
            record = {"time": datetime.now(UTC).isoformat(), "phase": label, "state": vars(state)}
            records.append(record)
            print(json.dumps(record), flush=True)
            await asyncio.sleep(args.hold)
    finally:
        try:
            await client._write(connection, protocol.power(False))
            await asyncio.sleep(0.15)
            state = await client._query(connection)
            print(f"FINISHED: power off confirmed ({state.on=})", flush=True)
        finally:
            await connection.disconnect()
            await client.close()
            target = Path(args.output)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(records, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--address", required=True)
    parser.add_argument("--hold", type=float, default=10)
    parser.add_argument("--color-order", choices=["RGB", "BGR"], default="BGR")
    parser.add_argument("--output", default="captures/visual-test.json")
    asyncio.run(main(parser.parse_args()))
