"""Tests for netlist parsing and connection tracing."""

import asyncio

import pytest

from kicad_mcp_server.parsers.netlist_parser import NetlistParser
from kicad_mcp_server.tools.netlist import trace_netlist_connection

NETLIST = """<?xml version="1.0" encoding="UTF-8"?>
<export version="E">
  <components>
    <comp ref="R1"><value>10k</value><libsource lib="Device" part="R"/></comp>
    <comp ref="R2"><value>4k7</value><libsource lib="Device" part="R"/></comp>
    <comp ref="U1"><value>MCU</value><libsource lib="Device" part="U"/></comp>
  </components>
  <nets>
    <net code="1" name="SIG">
      <node ref="R1" pin="1" pintype="passive"/>
      <node ref="R2" pin="1" pintype="passive"/>
    </net>
    <net code="2" name="GND">
      <node ref="U1" pin="1" pintype="power_in"/>
      <node ref="U1" pin="2" pintype="power_in"/>
      <node ref="R1" pin="2" pintype="passive"/>
    </net>
  </nets>
</export>
"""


@pytest.fixture
def netlist_path(tmp_path):
    path = tmp_path / "board.xml"
    path.write_text(NETLIST, encoding="utf-8")
    return path


class TestNetlistParser:
    def test_components_include_pins(self, netlist_path):
        components = NetlistParser(str(netlist_path)).get_components()
        assert set(components) == {"R1", "R2", "U1"}
        assert components["R1"].pins == {"1": "SIG", "2": "GND"}
        # Two pins of U1 are on the same net and must both survive parsing.
        assert components["U1"].pins == {"1": "GND", "2": "GND"}

    def test_nets_include_nodes(self, netlist_path):
        nets = NetlistParser(str(netlist_path)).get_nets()
        assert ("R1", "1") in nets["SIG"].pins
        assert ("R2", "1") in nets["SIG"].pins
        assert ("U1", "2") in nets["GND"].pins


class TestTraceNetlistConnection:
    def test_trace_all_pins_of_component(self, netlist_path):
        """Regression: the parser groups pins per net as a list; the tool used
        to index it as a single dict and crashed with
        'list indices must be integers or slices, not str'."""
        result = asyncio.run(trace_netlist_connection(str(netlist_path), "U1"))

        assert "## Netlist Connection Trace: U1" in result
        assert "### Net: GND" in result
        # Both GND pins are reported.
        assert "**Pin:** 1" in result
        assert "**Pin:** 2" in result
        # The trace lists the other component on the net.
        assert "| R1 | 2 |" in result

    def test_trace_single_pin(self, netlist_path):
        result = asyncio.run(trace_netlist_connection(str(netlist_path), "R1", "1"))

        assert "**Net:** SIG" in result
        assert "| R2 | 1 |" in result

    def test_unknown_component_is_reported(self, netlist_path):
        result = asyncio.run(trace_netlist_connection(str(netlist_path), "X9"))
        assert "not found" in result
