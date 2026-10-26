"""Tests for PCB tool parser selection."""

import pytest

from kicad_mcp_server.parsers import pcb_parser, pcb_parser_kicad
from kicad_mcp_server.tools import pcb


class TestGetParser:
    def test_falls_back_to_text_parser_without_pcbnew(self, monkeypatch):
        sentinel = object()

        def no_pcbnew(self, file_path):
            raise ImportError("pcbnew module not found")

        monkeypatch.setattr(pcb_parser_kicad.PCBParserKiCad, "__init__", no_pcbnew)
        monkeypatch.setattr(pcb_parser, "PCBParser", lambda path: sentinel)

        assert pcb._get_parser("board.kicad_pcb") is sentinel

    def test_load_failure_is_not_hidden_by_fallback(self, monkeypatch):
        """A board pcbnew cannot load must raise, not silently produce the
        text parser's (wrong) statistics."""

        def cannot_load(self, file_path):
            raise ValueError("KiCad could not load the board")

        monkeypatch.setattr(pcb_parser_kicad.PCBParserKiCad, "__init__", cannot_load)
        monkeypatch.setattr(
            pcb_parser, "PCBParser", lambda path: pytest.fail("text parser must not be used")
        )

        with pytest.raises(ValueError, match="could not load"):
            pcb._get_parser("board.kicad_pcb")
