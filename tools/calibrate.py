"""Hold one known lighting command for a human to inspect; no controller settings."""

import argparse
import asyncio
import importlib
import sys
import types
from pathlib import Path

from bleak import BleakScanner

package = types.ModuleType("rug_calibration")
package.__path__ = [str(Path(__file__).resolve().parents[1] / "custom_components/mda_rug")]
sys.modules[package.__name__] = package
protocol = importlib.import_module("rug_calibration.protocol")
RugClient = importlib.import_module("rug_calibration.client").RugClient


async def main(args):
    if args.action == "off":
        commands = [protocol.power(False)]
    elif args.action == "color":
        commands = [
            protocol.power(True),
            protocol.color(args.hue, 100, args.brightness, args.color_order),
        ]
    elif args.action == "scene":
        commands = [
            protocol.power(True),
            protocol.scene(args.scene, 30, args.color_order, args.brightness),
        ]
    device = await BleakScanner.find_device_by_address(args.address, timeout=20)
    if device is None:
        raise RuntimeError("Rug not advertising; close the MDA app")
    client = RugClient(lambda: device, "MDA calibration")
    try:
        state = await client.execute(commands)
        print(f"Applied {args.action}, hue={args.hue}, brightness={args.brightness}; {state}")
    finally:
        await client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["color", "scene", "off"])
    parser.add_argument("--address", required=True)
    parser.add_argument("--hue", type=float, default=0)
    parser.add_argument("--brightness", type=int, default=30)
    parser.add_argument("--color-order", choices=["RGB", "BGR"], default="RGB")
    parser.add_argument("--scene", choices=list(protocol.SCENES), default="Northern Lights")
    asyncio.run(main(parser.parse_args()))
