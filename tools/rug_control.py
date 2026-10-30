"""Use the integration's restricted protocol against the confirmed rug from Windows."""

import argparse
import asyncio
import importlib.util
import json
import sys
import time
from pathlib import Path

from bleak import BleakClient, BleakScanner

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "mda_protocol", root / "custom_components/mda_rug/protocol.py"
)
protocol = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = protocol
spec.loader.exec_module(protocol)


async def main(args):
    device = await BleakScanner.find_device_by_address(args.address, timeout=20)
    if not device:
        raise RuntimeError("Rug is not advertising; close the phone app")
    records = []

    def received(_, data):
        parsed = protocol.parse_notification(bytes(data))
        row = {
            "time": time.time(),
            "notify": bytes(data).hex(),
            "state": vars(parsed) if parsed else None,
        }
        records.append(row)
        print(json.dumps(row), flush=True)

    async with BleakClient(device, timeout=20) as client:
        await client.start_notify(protocol.NOTIFY_UUID, received)
        if args.action == "scenes-test":
            commands = [("on", protocol.power(True))]
            for name in protocol.SCENES:
                commands.extend([(name, protocol.scene(name, 30, "BGR", 25))])
            commands.append(("off", protocol.power(False)))
        elif args.action == "color-test":
            commands = [
                ("on", protocol.power(True)),
                ("red", protocol.color(0, 100, 30, "BGR")),
                ("blue", protocol.color(240, 100, 20, "BGR")),
                ("off", protocol.power(False)),
            ]
        else:
            commands = []
        commands.insert(0, ("query", protocol.query()))
        try:
            for seq, (label, payload) in enumerate(commands, 1):
                packet = protocol.frame(payload, seq * 2)
                print(label, packet.hex(), flush=True)
                records.append({"time": time.time(), "action": label, "write": packet.hex()})
                await client.write_gatt_char(protocol.WRITE_UUID, packet, response=False)
                await asyncio.sleep(2)
                await client.write_gatt_char(
                    protocol.WRITE_UUID,
                    protocol.frame(protocol.query(), seq * 2 + 1),
                    response=False,
                )
                await asyncio.sleep(2)
        finally:
            Path(args.output).write_text(json.dumps(records, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["status", "scenes-test", "color-test"])
    parser.add_argument("--address", required=True)
    parser.add_argument("--output", default="captures/control-test.json")
    asyncio.run(main(parser.parse_args()))
