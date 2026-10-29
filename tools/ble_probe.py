"""Read BLE advertisements or inspect one device's GATT services; never write."""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from bleak import BleakClient, BleakScanner


async def run(args):
    found = await BleakScanner.discover(timeout=args.seconds, return_adv=True)
    rows = []
    for device, adv in found.values():
        rows.append(
            {
                "address": device.address,
                "name": adv.local_name or device.name,
                "rssi": adv.rssi,
                "service_uuids": adv.service_uuids,
                "manufacturer_data": {str(k): v.hex() for k, v in adv.manufacturer_data.items()},
                "service_data": {k: v.hex() for k, v in adv.service_data.items()},
            }
        )
    result = {"captured_at": datetime.now(UTC).isoformat(), "devices": rows}
    if args.address:
        target = next(
            (d for d, _ in found.values() if d.address.lower() == args.address.lower()), None
        )
        if target is None:
            raise RuntimeError("Target was not advertising. Close the phone app and retry.")
        async with BleakClient(target, timeout=20) as client:
            result["gatt"] = [
                {
                    "uuid": s.uuid,
                    "handle": s.handle,
                    "characteristics": [
                        {
                            "uuid": c.uuid,
                            "handle": c.handle,
                            "properties": c.properties,
                            "descriptors": [
                                {"uuid": d.uuid, "handle": d.handle} for d in c.descriptors
                            ],
                        }
                        for c in s.characteristics
                    ],
                }
                for s in client.services
            ]
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    for row in sorted(rows, key=lambda r: r["rssi"], reverse=True):
        print(
            f"{row['address']} {row['rssi']:4} {row['name'] or '(unnamed)'} {row['service_uuids']}"
        )
    if "gatt" in result:
        print(json.dumps(result["gatt"], indent=2))
    print(f"Saved {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=15)
    parser.add_argument("--address", help="Inspect GATT for this exact address")
    parser.add_argument("--output", default="captures/scan.json")
    asyncio.run(run(parser.parse_args()))
