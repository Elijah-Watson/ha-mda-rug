"""Load hardware-independent modules without requiring the HA runtime on Windows."""

import importlib
import sys
import types
from pathlib import Path

import pytest

package = types.ModuleType("mda_test")
package.__path__ = [str(Path(__file__).resolve().parents[1] / "custom_components/mda_rug")]
sys.modules[package.__name__] = package
protocol_module = importlib.import_module("mda_test.protocol")
client_module = importlib.import_module("mda_test.client")


@pytest.fixture
def protocol():
    return protocol_module


@pytest.fixture
def client_module_fixture():
    return client_module
