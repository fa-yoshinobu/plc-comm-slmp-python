"""Tests for SLMP client and core functions."""

import json
import unittest
import warnings
from pathlib import Path
from subprocess import CompletedProcess
from tempfile import TemporaryDirectory
from typing import Any, NoReturn
from unittest.mock import patch

import slmp.core
from slmp import cli
from slmp.client import (
    BlockReadResult,
    LabelArrayReadPoint,
    LabelArrayReadResult,
    LabelArrayWritePoint,
    LabelRandomReadResult,
    LabelRandomWritePoint,
    LongTimerResult,
    MonitorResult,
    RandomReadResult,
    SlmpClient,
    TypeNameInfo,
    _recv_exact,
    _recv_tcp_frame,
)
from slmp.constants import Command, FrameType, PLCSeries
from slmp.core import (
    ExtensionSpec,
    SlmpBoundaryBehaviorWarning,
    SlmpError,
    SlmpPracticalPathWarning,
    SlmpResponse,
    SlmpTarget,
    SlmpUnsupportedDeviceError,
    build_device_modification_flags,
    decode_4e_response,
    encode_4e_request,
    encode_device_spec,
    encode_extended_device_spec,
    pack_bit_values,
    parse_device,
    parse_extended_device,
    unpack_bit_values,
)

print(f"DEBUG: core file = {slmp.core.__file__}")


class FakeClient(SlmpClient):
    """Fake SLMP client for testing."""

    def __init__(self) -> None:
        """Initialize FakeClient."""
        super().__init__("127.0.0.1")
        self.last_request: tuple[int, int, bytes, dict[str, Any]] | None = None
        self.requests: list[tuple[int, int, bytes, dict[str, Any]]] = []
        self.next_response_data = b""
        self.next_response_end_code = 0
        self.response_queue: list[tuple[int, bytes]] = []
        self.last_no_response: tuple[int, int, bytes, dict[str, Any]] | None = None

    def request(
        self,
        command: int | Command,
        subcommand: int = 0x0000,
        data: bytes = b"",
        *,
        serial: int | None = None,
        target: SlmpTarget | None = None,
        monitoring_timer: int | None = None,
        raise_on_error: bool | None = None,
    ) -> SlmpResponse:
        """Mock request method."""
        cmd = int(command)
        kwargs = {
            "serial": serial,
            "target": target,
            "monitoring_timer": monitoring_timer,
            "raise_on_error": raise_on_error,
        }
        self.last_request = (cmd, subcommand, data, kwargs)
        self.requests.append(self.last_request)
        if self.response_queue:
            end_code, response_data = self.response_queue.pop(0)
        else:
            end_code = self.next_response_end_code
            response_data = self.next_response_data
        do_raise = self.raise_on_error if raise_on_error is None else raise_on_error
        if do_raise and end_code != 0:
            raise SlmpError(
                f"SLMP error end_code=0x{end_code:04X} command=0x{cmd:04X} subcommand=0x{subcommand:04X}",
                end_code=end_code,
                data=response_data,
            )
        return SlmpResponse(
            serial=0,
            target=SlmpTarget(),
            end_code=end_code,
            data=response_data,
            raw=b"",
        )

    def _send_no_response(
        self,
        command: int | Command,
        subcommand: int,
        data: bytes,
        *,
        serial: int | None = None,
        target: SlmpTarget | None = None,
        monitoring_timer: int | None = None,
    ) -> None:
        cmd = int(command)
        kwargs = {
            "serial": serial,
            "target": target,
            "monitoring_timer": monitoring_timer,
        }
        self.last_no_response = (cmd, subcommand, data, kwargs)


class _RecvIntoSocket:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = chunks[:]

    def recv_into(self, view: memoryview) -> int:
        if not self._chunks:
            return 0
        chunk = self._chunks.pop(0)
        size = min(len(view), len(chunk))
        view[:size] = chunk[:size]
        if size < len(chunk):
            self._chunks.insert(0, chunk[size:])
        return size


class _RecvOnlySocket:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = chunks[:]

    def recv(self, size: int) -> bytes:
        if not self._chunks:
            return b""
        chunk = self._chunks.pop(0)
        data = chunk[:size]
        if size < len(chunk):
            self._chunks.insert(0, chunk[size:])
        return data


class TestReceiveHelpers(unittest.TestCase):
    def test_recv_exact_prefers_recv_into(self) -> None:
        sock = _RecvIntoSocket([b"\x01", b"\x02\x03"])
        self.assertEqual(_recv_exact(sock, 3), b"\x01\x02\x03")

    def test_recv_exact_falls_back_to_recv(self) -> None:
        sock = _RecvOnlySocket([b"\x10\x20", b"\x30"])
        self.assertEqual(_recv_exact(sock, 3), b"\x10\x20\x30")

    def test_recv_tcp_frame_returns_complete_3e_response(self) -> None:
        frame = bytes.fromhex("d00000ffff030002000000")
        sock = _RecvIntoSocket([frame[:4], frame[4:7], frame[7:]])
        self.assertEqual(_recv_tcp_frame(sock, frame_type=FrameType.FRAME_3E), frame)


class TestTypedHelpers(unittest.TestCase):
    """TestTypedHelpers class."""

    def test_read_dword_helper_uses_low_word_first(self) -> None:
        """Test test_read_dword_helper_uses_low_word_first."""
        client = FakeClient()
        client.next_response_data = b"\x78\x56\x34\x12"

        value = client.read_dword("D100")

        self.assertEqual(value, 0x12345678)
        assert client.last_request is not None
        self.assertEqual(client.last_request[0], int(Command.DEVICE_READ))
        self.assertEqual(client.last_request[2][-2:], b"\x02\x00")

    def test_write_float32_helper_uses_low_word_first(self) -> None:
        """Test test_write_float32_helper_uses_low_word_first."""
        client = FakeClient()

        client.write_float32("D100", 1.5)

        assert client.last_request is not None
        self.assertEqual(client.last_request[0], int(Command.DEVICE_WRITE))
        self.assertEqual(client.last_request[2][-4:], b"\x00\x00\xc0\x3f")

    def test_register_monitor_devices_alias_uses_monitor_command(self) -> None:
        """Test test_register_monitor_devices_alias_uses_monitor_command."""
        client = FakeClient()

        client.register_monitor_devices(word_devices=["D100"], dword_devices=["D200"])

        assert client.last_request is not None
        self.assertEqual(client.last_request[0], int(Command.DEVICE_ENTRY_MONITOR))

    def test_read_random_labels_alias_uses_label_read_random(self) -> None:
        """Test test_read_random_labels_alias_uses_label_read_random."""
        client = FakeClient()
        client.next_response_data = b"\x01\x00\x01\x00\x02\x00OK"

        result = client.read_random_labels(["LABEL_A"])

        self.assertEqual(len(result), 1)
        assert client.last_request is not None
        self.assertEqual(client.last_request[0], int(Command.LABEL_READ_RANDOM))


class TestCodec(unittest.TestCase):
    """TestCodec class."""

    def test_encode_4e_request(self) -> None:
        """Test test_encode_4e_request."""
        frame = encode_4e_request(
            serial=0x1234,
            target=SlmpTarget(network=1, station=2, module_io=0x03FF, multidrop=0),
            monitoring_timer=0x0010,
            command=0x0401,
            subcommand=0x0000,
            data=b"\xaa\xbb",
        )
        self.assertEqual(frame[:2], b"\x54\x00")
        self.assertEqual(frame[2:4], b"\x34\x12")
        self.assertEqual(frame[6], 1)
        self.assertEqual(frame[7], 2)
        self.assertEqual(frame[8:10], b"\xff\x03")
        self.assertEqual(frame[11:13], (8).to_bytes(2, "little"))  # timer + cmd + subcmd + 2-byte payload
        self.assertEqual(frame[13:15], b"\x10\x00")
        self.assertEqual(frame[15:17], b"\x01\x04")
        self.assertEqual(frame[17:19], b"\x00\x00")
        self.assertEqual(frame[19:], b"\xaa\xbb")

    def test_decode_4e_response(self) -> None:
        """Test test_decode_4e_response."""
        # D4 00 / serial / reserve / dest / len / endcode / data
        frame = (
            b"\xd4\x00"
            + b"\x34\x12"
            + b"\x00\x00"
            + b"\x01\x02\xff\x03\x00"
            + b"\x06\x00"
            + b"\x00\x00"
            + b"\x11\x22\x33\x44"
        )
        resp = decode_4e_response(frame)
        self.assertEqual(resp.serial, 0x1234)
        self.assertEqual(resp.target.network, 1)
        self.assertEqual(resp.target.station, 2)
        self.assertEqual(resp.end_code, 0)
        self.assertEqual(resp.data, b"\x11\x22\x33\x44")

    def test_device_and_bit_helpers(self) -> None:
        """Test test_device_and_bit_helpers."""
        self.assertEqual(str(parse_device("D100")), "D100")
        self.assertEqual(str(parse_device("X20")), "X20")
        self.assertEqual(encode_device_spec("D100", series=PLCSeries.QL), b"\x64\x00\x00\xa8")
        self.assertEqual(encode_device_spec("D100", series=PLCSeries.IQR), b"\x64\x00\x00\x00\xa8\x00")
        self.assertEqual(encode_device_spec("R32767", series=PLCSeries.IQR), b"\xff\x7f\x00\x00\xaf\x00")
        with self.assertRaises(ValueError):
            encode_device_spec("R32768", series=PLCSeries.QL)
        with self.assertRaises(ValueError):
            encode_device_spec("R32768", series=PLCSeries.IQR)

        raw = pack_bit_values([1, 0, 1, 1, 0])
        self.assertEqual(raw, b"\x10\x11\x00")
        bits = unpack_bit_values(raw, 5)
        self.assertEqual(bits, [True, False, True, True, False])
        extended_device = parse_extended_device(r"U3E0\G10")
        self.assertEqual(str(extended_device.ref), "G10")
        self.assertEqual(extended_device.extension_specification, 0x03E0)
        extended_device_ql = parse_extended_device(r"U01\G22")
        self.assertEqual(str(extended_device_ql.ref), "G22")
        self.assertEqual(extended_device_ql.extension_specification, 0x0001)

    def test_extension_helpers(self) -> None:
        """Test test_extension_helpers."""
        flags_ql = build_device_modification_flags(
            series=PLCSeries.QL,
            use_indirect_specification=True,
            register_mode="z",
        )
        self.assertEqual(flags_ql, 0x48)

        # 0xF9 = LINK_DIRECT: uses GOT pcap-verified format (j_net from extension_specification)
        # J1\W100 (W hex 0x100=256): 00 00 | 00 01 00 | b4 | 00 00 | 01 | 00 | f9
        ext = ExtensionSpec(
            extension_specification=0x0001,
            direct_memory_specification=0xF9,
        )
        data = encode_extended_device_spec("W100", series=PLCSeries.QL, extension=ext)
        self.assertEqual(data, b"\x00\x00\x00\x01\x00\xb4\x00\x00\x01\x00\xf9")

        cpu_ext = ExtensionSpec(
            extension_specification=0x03E0,
            extension_specification_modification=0x00,
            device_modification_index=0x00,
            device_modification_flags=0x00,
            direct_memory_specification=0xFA,
        )
        g_data = encode_extended_device_spec("G10", series=PLCSeries.IQR, extension=cpu_ext)
        self.assertEqual(g_data, b"\x00\x00\x0a\x00\x00\x00\xab\x00\x00\x00\xe0\x03\xfa")
        hg_data = encode_extended_device_spec("HG20", series=PLCSeries.IQR, extension=cpu_ext)
        self.assertEqual(hg_data, b"\x00\x00\x14\x00\x00\x00\x2e\x00\x00\x00\xe0\x03\xfa")
        qualified_g_data = encode_extended_device_spec(
            r"U3E0\G10",
            series=PLCSeries.IQR,
            extension=ExtensionSpec(
                extension_specification=0x0000,
                extension_specification_modification=0x00,
                device_modification_index=0x00,
                device_modification_flags=0x00,
                direct_memory_specification=0xFA,
            ),
        )
        self.assertEqual(qualified_g_data, g_data)
        module_ext = ExtensionSpec(
            extension_specification=0x0001,
            extension_specification_modification=0x00,
            device_modification_index=0x00,
            device_modification_flags=0x00,
            direct_memory_specification=0xF8,
        )
        ql_g_data = encode_extended_device_spec("G22", series=PLCSeries.QL, extension=module_ext)
        self.assertEqual(ql_g_data, b"\x00\x00\x16\x00\x00\xab\x00\x00\x01\x00\xf8")
        qualified_ql_g_data = encode_extended_device_spec(
            r"U01\G22",
            series=PLCSeries.QL,
            extension=ExtensionSpec(
                extension_specification=0x0000,
                extension_specification_modification=0x00,
                device_modification_index=0x00,
                device_modification_flags=0x00,
                direct_memory_specification=0xF8,
            ),
        )
        self.assertEqual(qualified_ql_g_data, ql_g_data)

    def test_parse_named_target(self) -> None:
        """Test test_parse_named_target."""
        parsed = cli._parse_named_target("NW1-ST2")
        self.assertEqual(parsed.name, "NW1-ST2")
        self.assertEqual(parsed.target.network, 0x01)
        self.assertEqual(parsed.target.station, 0x02)
        self.assertEqual(parsed.target.module_io, 0x03FF)
        self.assertEqual(parsed.target.multidrop, 0x00)

    def test_parse_named_target_self(self) -> None:
        """Test test_parse_named_target_self."""
        parsed = cli._parse_named_target("self")
        self.assertEqual(parsed.name, "SELF")
        self.assertEqual(parsed.target.network, 0x00)
        self.assertEqual(parsed.target.station, 0xFF)
        self.assertEqual(parsed.target.module_io, 0x03FF)
        self.assertEqual(parsed.target.multidrop, 0x00)

    def test_parse_named_target_self_cpu(self) -> None:
        """Test test_parse_named_target_self_cpu."""
        parsed = cli._parse_named_target("self-cpu2")
        self.assertEqual(parsed.name, "SELF-CPU2")
        self.assertEqual(parsed.target.network, 0x00)
        self.assertEqual(parsed.target.station, 0xFF)
        self.assertEqual(parsed.target.module_io, 0x03E1)
        self.assertEqual(parsed.target.multidrop, 0x00)

    def test_parse_named_target_rejects_invalid_shorthand(self) -> None:
        """Test test_parse_named_target_rejects_invalid_shorthand."""
        with self.assertRaises(ValueError):
            cli._parse_named_target("remote1")

    def test_parse_named_target_rejects_self_mismatch(self) -> None:
        """Test test_parse_named_target_rejects_self_mismatch."""
        with self.assertRaises(ValueError):
            cli._parse_named_target("SELF,0x00,0x01,0x03FF,0x00")

    def test_parse_named_target_rejects_self_cpu_module_io_mismatch(self) -> None:
        """Test test_parse_named_target_rejects_self_cpu_module_io_mismatch."""
        with self.assertRaises(ValueError):
            cli._parse_named_target("SELF-CPU1,0x00,0xFF,0x03E1,0x00")

    def test_load_named_targets_from_file(self) -> None:
        """Test test_load_named_targets_from_file."""
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "targets.txt"
            path.write_text("# comment\nSELF\nSELF-CPU1\nNW1-ST2\n", encoding="utf-8")
            loaded = cli._load_named_targets(None, str(path))
        self.assertEqual(len(loaded), 3)
        self.assertEqual(loaded[0].name, "SELF")
        self.assertEqual(loaded[0].target.station, 0xFF)
        self.assertEqual(loaded[1].name, "SELF-CPU1")
        self.assertEqual(loaded[1].target.module_io, 0x03E0)
        self.assertEqual(loaded[2].name, "NW1-ST2")
        self.assertEqual(loaded[2].target.network, 0x01)
        self.assertEqual(loaded[2].target.station, 0x02)

    def test_render_compatibility_matrix_markdown(self) -> None:
        """Test test_render_compatibility_matrix_markdown."""
        content = cli._render_compatibility_matrix_markdown(
            [
                {
                    "plc_label": "PLC-A",
                    "results": [
                        {
                            "frame_type": "3e",
                            "access_profile": "ql",
                            "detected_model": "Q26UDEHCPU",
                            "commands": [
                                {"code": "0101", "status": "OK"},
                                {"code": "0401", "status": "OK"},
                                {"code": "1406", "status": "NG", "detail": "end_code=0xC05B"},
                            ],
                        },
                        {
                            "frame_type": "4e",
                            "access_profile": "iqr",
                            "commands": [
                                {"code": "0101", "status": "NG", "detail": "type_name=NG (end_code=0xC059)"},
                                {"code": "1406", "status": "OK"},
                            ],
                        },
                    ],
                },
                {
                    "plc_label": "PLC-B",
                    "results": [
                        {
                            "frame_type": "4e",
                            "access_profile": "ql",
                            "detected_model": "FX5UC-32MT/D",
                            "commands": [
                                {"code": "0101", "status": "OK"},
                                {"code": "0401", "status": "OK"},
                            ],
                        }
                    ],
                },
            ],
            source_paths=[Path("probe_a.json"), Path("probe_b.json")],
        )
        self.assertIn("| PLC | Detected Model | **0101** | **0401** |", content)
        self.assertIn("| PLC-A | Q26UDEHCPU | PARTIAL | YES |", content)
        self.assertIn("`PLC-A`: combos=3e/ql, 4e/iqr, detected_model=Q26UDEHCPU", content)
        self.assertIn("## 3. Aggregated Non-OK Reasons", content)
        self.assertIn("| 0xC059 | 1 | PLC-A | 0101 | 4e/iqr |", content)
        self.assertIn("## 4. Practical Recommended Profiles", content)
        self.assertIn("`PLC-A`: prefer 3e/ql", content)
        self.assertIn("## 5. Non-Recommended Combinations", content)
        self.assertIn("## 6. Product-Family Conclusions", content)
        self.assertIn("## 7. Detailed PARTIAL or NO Breakdown", content)
        self.assertIn("`1406 Block Write`: 3e/ql=NG (0xC05B); 4e/iqr=OK", content)

    def test_render_compatibility_matrix_markdown_adds_module_endpoint_note(self) -> None:
        """Test test_render_compatibility_matrix_markdown_adds_module_endpoint_note."""
        content = cli._render_compatibility_matrix_markdown(
            [
                {
                    "plc_label": "RJ71EN71",
                    "results": [
                        {
                            "frame_type": "3e",
                            "access_profile": "ql",
                            "detected_model": "R08CPU",
                            "commands": [{"code": "0101", "status": "OK", "detail": "model=R08CPU"}],
                        }
                    ],
                }
            ],
            source_paths=[Path("probe.json")],
        )
        self.assertIn("note=Ethernet module endpoint;", content)

    def test_render_compatibility_matrix_markdown_sorts_rows_and_omits_pending_columns(self) -> None:
        """Test test_render_compatibility_matrix_markdown_sorts_rows_and_omits_pending_columns."""
        content = cli._render_compatibility_matrix_markdown(
            [
                {
                    "plc_label": "FX5U",
                    "results": [
                        {"frame_type": "3e", "access_profile": "ql", "commands": [{"code": "0101", "status": "OK"}]}
                    ],
                },
                {
                    "plc_label": "Q26UDEHCPU_SN20081",
                    "results": [
                        {"frame_type": "3e", "access_profile": "ql", "commands": [{"code": "0101", "status": "NG"}]}
                    ],
                },
                {
                    "plc_label": "R08CPU",
                    "results": [
                        {"frame_type": "3e", "access_profile": "ql", "commands": [{"code": "0101", "status": "OK"}]}
                    ],
                },
            ],
            source_paths=[Path("probe.json")],
            omit_pending_columns=True,
        )
        self.assertIn("- Omit all-PENDING columns: yes", content)
        self.assertNotIn("**1401**", content)
        self.assertLess(content.index("| R08CPU |"), content.index("| Q26UDEHCPU_SN20081 |"))
        self.assertLess(content.index("| Q26UDEHCPU_SN20081 |"), content.index("| FX5U |"))

    def test_build_compatibility_policy_prefers_family_profiles(self) -> None:
        """Test test_build_compatibility_policy_prefers_family_profiles."""
        policy = cli._build_compatibility_policy(
            [
                {
                    "plc_label": "R08CPU",
                    "results": [
                        {
                            "frame_type": "4e",
                            "access_profile": "iqr",
                            "detected_model": "R08CPU",
                            "commands": [{"code": "0401", "status": "OK"}],
                        },
                        {
                            "frame_type": "3e",
                            "access_profile": "ql",
                            "detected_model": "R08CPU",
                            "commands": [{"code": "0401", "status": "NG", "detail": "timed out"}],
                        },
                    ],
                },
                {
                    "plc_label": "Q26UDEHCPU_SN20081",
                    "results": [
                        {
                            "frame_type": "3e",
                            "access_profile": "ql",
                            "detected_model": "Q26UDEHCPU",
                            "commands": [{"code": "0401", "status": "OK"}],
                        }
                    ],
                },
            ]
        )
        self.assertEqual(policy["families"]["iQ-R"]["preferred_profiles"][0], "4e/iqr")
        self.assertEqual(policy["families"]["MELSEC-Q"]["preferred_profiles"][0], "3e/ql")
        self.assertEqual(policy["models"]["R08CPU"]["preferred_profiles"][0], "4e/iqr")

    def test_parse_boundary_spec(self) -> None:
        """Test test_parse_boundary_spec."""
        parsed = cli._parse_boundary_spec("D,D10239,word")
        self.assertEqual(parsed.label, "D")
        self.assertEqual(parsed.last_device, "D10239")
        self.assertFalse(parsed.bit_unit)
        self.assertEqual(parsed.span_points, 1)

        parsed = cli._parse_boundary_spec("X,X2FFF,bit,1")
        self.assertEqual(parsed.last_device, "X2FFF")
        self.assertTrue(parsed.bit_unit)
        self.assertEqual(parsed.span_points, 1)

        parsed = cli._parse_boundary_spec("LTN,LTN1023,word,4")
        self.assertEqual(parsed.span_points, 4)

    def test_load_boundary_specs_from_file(self) -> None:
        """Test test_load_boundary_specs_from_file."""
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "ranges.txt"
            path.write_text("# comment\nD,D10239,word\nLTN,LTN1023,word,4\n", encoding="utf-8")
            loaded = cli._load_boundary_specs(None, str(path))
        self.assertEqual(len(loaded), 2)
        self.assertEqual(loaded[0].last_device, "D10239")
        self.assertEqual(loaded[1].last_device, "LTN1023")
        self.assertFalse(loaded[1].bit_unit)
        self.assertEqual(loaded[1].span_points, 4)

    def test_increment_device_text_uses_device_radix(self) -> None:
        """Test test_increment_device_text_uses_device_radix."""
        self.assertEqual(cli._increment_device_text("D10239"), "D10240")
        self.assertEqual(cli._increment_device_text("X2FFF"), "X3000")
        self.assertEqual(cli._increment_device_text("ZR163839"), "ZR163840")
        self.assertEqual(cli._offset_device_text("D1000", 25), "D1025")
        self.assertEqual(cli._offset_device_text("X20", 0x10), "X30")

    def test_parse_focused_boundary_spec(self) -> None:
        """Test test_parse_focused_boundary_spec."""
        parsed = cli._parse_focused_boundary_spec("ZR,ZR163839,word,1/2/3/16/64,1/2")
        self.assertEqual(parsed.label, "ZR")
        self.assertEqual(parsed.edge_device, "ZR163839")
        self.assertFalse(parsed.bit_unit)
        self.assertEqual(parsed.edge_points, (1, 2, 3, 16, 64))
        self.assertEqual(parsed.next_points, (1, 2))

    def test_load_focused_boundary_specs_defaults_when_unspecified(self) -> None:
        """Test test_load_focused_boundary_specs_defaults_when_unspecified."""
        loaded = cli._load_focused_boundary_specs(None, None)
        self.assertGreaterEqual(len(loaded), 1)
        self.assertEqual(loaded[0].label, "Z")

    def test_model_scoped_default_paths(self) -> None:
        """Test test_model_scoped_default_paths."""
        self.assertEqual(
            cli._default_report_output(series="iqr", model="R08CPU", filename="probe_latest.md"),
            str(Path("internal_docs") / "iqr_r08cpu" / "probe_latest.md"),
        )
        self.assertEqual(
            cli._default_capture_dir(series="iqr", model="R08CPU", dirname="frame_dumps_extended_device"),
            Path("internal_docs") / "iqr_r08cpu" / "frame_dumps_extended_device",
        )
        self.assertEqual(
            cli._resolve_capture_dir(
                output_dir=None,
                series="iqr",
                model="R08CPU",
                dirname="frame_dumps_extended_device",
            ),
            Path("internal_docs") / "iqr_r08cpu" / "frame_dumps_extended_device",
        )

    def test_write_markdown_report_creates_latest_and_archive(self) -> None:
        """Test test_write_markdown_report_creates_latest_and_archive."""
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "internal_docs" / "iqr_r08cpu" / "probe_latest.md"
            cli._write_markdown_report(
                str(output),
                title="# Probe",
                header_lines=["- Host: 127.0.0.1"],
                rows=[("0101", "OK", "model=R08CPU")],
            )

            self.assertTrue(output.exists())
            archive_dir = output.parent / "archive"
            self.assertTrue(archive_dir.exists())
            archived = list(archive_dir.glob("probe_*.md"))
            self.assertEqual(len(archived), 1)
            self.assertIn("| 0101 | OK | model=R08CPU |", output.read_text(encoding="utf-8"))
            self.assertEqual(output.read_text(encoding="utf-8"), archived[0].read_text(encoding="utf-8"))

    def test_initialize_model_docs_creates_scaffold(self) -> None:
        """Test test_initialize_model_docs_creates_scaffold."""
        with TemporaryDirectory() as tmp:
            model_dir, created, skipped = cli._initialize_model_docs(
                root=Path(tmp),
                series="iqr",
                model="R08CPU",
            )
            self.assertEqual(model_dir, Path(tmp) / "iqr_r08cpu")
            self.assertEqual(skipped, [])
            self.assertTrue((model_dir / "README.md").exists())
            self.assertTrue((model_dir / "device_access_matrix.csv").exists())
            self.assertTrue((model_dir / "current_plc_boundary_specs_example.txt").exists())
            self.assertTrue((model_dir / "current_register_boundary_focus_specs_example.txt").exists())
            self.assertTrue((model_dir / "other_station_targets_example.txt").exists())
            self.assertTrue((model_dir / "wireshark" / "README.md").exists())
            self.assertTrue((model_dir / "frame_dumps_extended_device").exists())
            self.assertGreaterEqual(len(created), 6)

            _, created2, skipped2 = cli._initialize_model_docs(
                root=Path(tmp),
                series="iqr",
                model="R08CPU",
            )
            self.assertEqual(created2, [])
            self.assertGreaterEqual(len(skipped2), 6)

    def test_load_device_access_matrix_rows(self) -> None:
        """Test test_load_device_access_matrix_rows."""
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "device_access_matrix.csv"
            path.write_text(
                "\n".join(
                    [
                        "device_code,device,kind,unsupported,read,write,note,manual_write,manual_write_note",
                        "D,D1000,word,,OK,OK,representative verification address,OK,human confirmed",
                        "LTC,LTC10,bit,YES,NG,SKIP,known direct-path issue,,",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            rows = cli._load_device_access_matrix_rows(path)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].device, "D1000")
        self.assertEqual(rows[0].manual_write, "OK")
        self.assertEqual(rows[1].unsupported, "YES")

    def test_render_device_access_matrix_markdown(self) -> None:
        """Test test_render_device_access_matrix_markdown."""
        rows = [
            cli.DeviceMatrixRow(
                "D",
                "D1000",
                "word",
                "",
                "OK",
                "OK",
                "representative verification address",
                "OK",
                "human confirmed",
            ),
            cli.DeviceMatrixRow("LTC", "LTC10", "bit", "YES", "NG", "SKIP", "known direct-path issue"),
        ]
        output = cli._render_device_access_matrix_markdown(
            rows,
            source_path=Path("internal_docs/iqr_r08cpu/device_access_matrix.csv"),
        )
        self.assertIn("# Device Access Matrix", output)
        self.assertIn("- word_read_OK: 1", output)
        self.assertIn("- bit_write_SKIP: 1", output)
        self.assertIn("- manual_write_OK: 1", output)
        self.assertIn(
            "| LTC | LTC10 | bit | YES | NG | SKIP |  | known direct-path issue |  |",
            output,
        )

    def test_select_manual_write_rows_filters_unsupported_and_non_writable(self) -> None:
        """Test test_select_manual_write_rows_filters_unsupported_and_non_writable."""
        rows = [
            cli.DeviceMatrixRow("D", "D1000", "word", "", "OK", "OK", ""),
            cli.DeviceMatrixRow("G", "G0", "extension_cpu_buffer", "", "NG", "SKIP", ""),
            cli.DeviceMatrixRow("M", "M1000", "bit", "YES", "OK", "OK", ""),
            cli.DeviceMatrixRow("ZR", "ZR1000", "word", "", "TODO", "TODO", ""),
        ]
        selected = cli._select_manual_write_rows(rows)
        self.assertEqual([row.device_code for row in selected], ["D", "ZR"])

    def test_select_manual_write_rows_allows_explicit_lt_lst_special_case(self) -> None:
        """Test test_select_manual_write_rows_allows_explicit_lt_lst_special_case."""
        rows = [
            cli.DeviceMatrixRow("LTC", "LTC10", "bit", "", "NG", "SKIP", "known direct-path issue"),
            cli.DeviceMatrixRow("LSTS", "LSTS10", "bit", "", "NG", "SKIP", "known direct-path issue"),
        ]
        selected = cli._select_manual_write_rows(rows, device_codes={"LTC"})
        self.assertEqual([row.device_code for row in selected], ["LTC"])

    def test_parse_manual_verdict(self) -> None:
        """Test test_parse_manual_verdict."""
        self.assertEqual(cli._parse_manual_verdict("Y"), "OK")
        self.assertEqual(cli._parse_manual_verdict("n"), "NG")
        self.assertEqual(cli._parse_manual_verdict("skip"), "SKIP")
        self.assertIsNone(cli._parse_manual_verdict("maybe"))

    def test_load_processed_manual_write_items(self) -> None:
        """Test test_load_processed_manual_write_items."""
        with TemporaryDirectory() as tmp:
            report = Path(tmp) / "manual_write_verification_latest.md"
            report.write_text(
                "\n".join(
                    [
                        "# Manual Write Verification Report",
                        "",
                        "| Item | Status | Detail |",
                        "|---|---|---|",
                        "| D D1000 | OK | before=0x0000, test=0x0001, restored=0x0000 |",
                        "| M M1000 | SKIP | operator skipped before write |",
                        "| W W100 | NG | temporary_write_failed=boom |",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            self.assertEqual(
                cli._load_processed_manual_write_items(report),
                {"D D1000", "M M1000", "W W100"},
            )
            self.assertEqual(
                cli._load_manual_write_report_rows(report),
                [
                    ("D D1000", "OK", "before=0x0000, test=0x0001, restored=0x0000"),
                    ("M M1000", "SKIP", "operator skipped before write"),
                    ("W W100", "NG", "temporary_write_failed=boom"),
                ],
            )

    def test_parse_positive_int_list(self) -> None:
        """Test test_parse_positive_int_list."""
        self.assertEqual(cli._parse_positive_int_list("1,2,4,8"), (1, 2, 4, 8))
        with self.assertRaises(ValueError):
            cli._parse_positive_int_list("1,0,2")

    def test_parse_label_array_probe_spec(self) -> None:
        """Test test_parse_label_array_probe_spec."""
        parsed = cli._parse_label_array_probe_spec("GGG.ZZZ.ZZZ.DDD[0]:1:20")
        self.assertEqual(parsed.label, "GGG.ZZZ.ZZZ.DDD[0]")
        self.assertEqual(parsed.unit_specification, 1)
        self.assertEqual(parsed.array_data_length, 20)

        with self.assertRaises(ValueError):
            cli._parse_label_array_probe_spec("DDD[0]:2:20")

    def test_make_manual_label_test_bytes(self) -> None:
        """Test test_make_manual_label_test_bytes."""
        self.assertEqual(cli._make_manual_label_test_bytes(b"\x00\x00"), b"\x01\x00")
        self.assertEqual(cli._make_manual_label_test_bytes(b"\x34\x12"), b"\x35\x12")
        with self.assertRaises(ValueError):
            cli._make_manual_label_test_bytes(b"")

    def test_summarize_durations(self) -> None:
        """Test test_summarize_durations."""
        stats = cli._summarize_durations([0.001, 0.002, 0.003, 0.004], elapsed_s=0.02)
        self.assertEqual(stats.count, 4)
        self.assertAlmostEqual(stats.avg_ms, 2.5)
        self.assertAlmostEqual(stats.max_ms, 4.0)
        self.assertAlmostEqual(stats.rate_per_s, 200.0)


class TestCli(unittest.TestCase):
    """TestCli class."""

    def test_connection_check_main_selects_frame_type(self) -> None:
        """Test test_connection_check_main_selects_frame_type."""

        class ConnectionCheckClient(SlmpClient):
            init_calls: list[tuple[str, str]] = []
            read_calls: list[tuple[str, int, bool, str | None]] = []
            type_name_calls: int = 0

            def __init__(
                self,
                host: str,
                port: int = 5000,
                *,
                transport: str = "tcp",
                timeout: float = 3.0,
                plc_series: PLCSeries | str = PLCSeries.QL,
                frame_type: cli.FrameType | str = cli.FrameType.FRAME_4E,
                default_target: SlmpTarget | None = None,
                monitoring_timer: int = 0x0010,
                raise_on_error: bool = True,
                trace_hook=None,
            ) -> None:
                super().__init__(
                    host,
                    port,
                    transport=transport,
                    timeout=timeout,
                    plc_series=plc_series,
                    frame_type=frame_type,
                    default_target=default_target,
                    monitoring_timer=monitoring_timer,
                    raise_on_error=raise_on_error,
                    trace_hook=trace_hook,
                )
                type(self).init_calls.append((self.frame_type.value, self.plc_series.value))

            def connect(self) -> None:
                return None

            def close(self) -> None:
                return None

            def read_devices(self, device, points, *, bit_unit=False, series=None):  # type: ignore[override]
                resolved_series = (
                    series.value if isinstance(series, PLCSeries) else (str(series) if series is not None else None)
                )
                type(self).read_calls.append((str(device), int(points), bool(bit_unit), resolved_series))
                return [True]

            def read_type_name(self) -> TypeNameInfo:
                type(self).type_name_calls += 1
                return TypeNameInfo(raw=b"\x00" * 18, model="Q26UDEHCPU", model_code=0x1234)

        with (
            patch.object(cli, "SlmpClient", ConnectionCheckClient),
            patch.object(cli, "_load_compatibility_policy", return_value=None),
        ):
            rc_default = cli.connection_check_main(["--host", "192.168.250.100", "--series", "ql"])
            rc_explicit = cli.connection_check_main(
                ["--host", "192.168.250.100", "--series", "ql", "--frame-type", "4e"]
            )

        self.assertEqual(rc_default, 0)
        self.assertEqual(rc_explicit, 0)
        self.assertEqual(ConnectionCheckClient.init_calls, [("3e", "ql"), ("4e", "ql")])
        self.assertEqual(ConnectionCheckClient.read_calls, [("SM400", 1, True, "ql"), ("SM400", 1, True, "ql")])
        self.assertEqual(ConnectionCheckClient.type_name_calls, 1)

    def test_connection_check_main_rejects_auto_series(self) -> None:
        """Test test_connection_check_main_rejects_auto_series."""

        with self.assertRaises(SystemExit) as cm:
            cli.connection_check_main(["--host", "192.168.250.100", "--series", "auto"])

        self.assertEqual(cm.exception.code, 2)

    def test_connection_check_main_uses_compatibility_policy_order(self) -> None:
        """Test test_connection_check_main_uses_compatibility_policy_order."""

        class PolicyConnectionCheckClient(SlmpClient):
            init_calls: list[tuple[str, str]] = []
            read_calls: list[tuple[str, int, bool, str | None]] = []

            def __init__(
                self,
                host: str,
                port: int = 5000,
                *,
                transport: str = "tcp",
                timeout: float = 3.0,
                plc_series: PLCSeries | str = PLCSeries.QL,
                frame_type: cli.FrameType | str = cli.FrameType.FRAME_4E,
                default_target: SlmpTarget | None = None,
                monitoring_timer: int = 0x0010,
                raise_on_error: bool = True,
                trace_hook=None,
            ) -> None:
                super().__init__(
                    host,
                    port,
                    transport=transport,
                    timeout=timeout,
                    plc_series=plc_series,
                    frame_type=frame_type,
                    default_target=default_target,
                    monitoring_timer=monitoring_timer,
                    raise_on_error=raise_on_error,
                    trace_hook=trace_hook,
                )
                type(self).init_calls.append((self.frame_type.value, self.plc_series.value))

            def connect(self) -> None:
                return None

            def close(self) -> None:
                return None

            def read_devices(self, device, points, *, bit_unit=False, series=None):  # type: ignore[override]
                resolved_series = (
                    series.value if isinstance(series, PLCSeries) else (str(series) if series is not None else None)
                )
                type(self).read_calls.append((str(device), int(points), bool(bit_unit), resolved_series))
                if self.frame_type.value != "4e" or resolved_series != "ql":
                    raise RuntimeError("policy should try 4e/ql first")
                return [True]

        with TemporaryDirectory() as tmp:
            policy_path = Path(tmp) / "compatibility_policy.json"
            policy_path.write_text(
                json.dumps({"global": {"preferred_profiles": ["4e/ql", "3e/ql", "4e/iqr", "3e/iqr"]}}),
                encoding="utf-8",
            )
            with patch.object(cli, "SlmpClient", PolicyConnectionCheckClient):
                rc = cli.connection_check_main(
                    [
                        "--host",
                        "192.168.250.100",
                        "--series",
                        "ql",
                        "--frame-type",
                        "4e",
                        "--compatibility-policy",
                        str(policy_path),
                    ]
                )

        self.assertEqual(rc, 0)
        self.assertEqual(PolicyConnectionCheckClient.init_calls, [("4e", "ql")])
        self.assertEqual(PolicyConnectionCheckClient.read_calls, [("SM400", 1, True, "ql")])

    def test_other_station_check_main_rejects_auto_series_and_frame(self) -> None:
        """Test test_other_station_check_main_rejects_auto_series_and_frame."""

        with self.assertRaises(SystemExit) as cm:
            cli.other_station_check_main(
                [
                    "--host",
                    "192.168.250.100",
                    "--series",
                    "auto",
                    "--frame-type",
                    "auto",
                    "--target",
                    "remote1,0x00,0x01,0x03FF,0x00",
                ]
            )

        self.assertEqual(cm.exception.code, 2)

    def test_other_station_check_main_type_name_failure_is_nonfatal(self) -> None:
        """Test test_other_station_check_main_type_name_failure_is_nonfatal."""

        class OtherStationTypeNameFailureClient(SlmpClient):
            read_calls: list[tuple[str, int, bool, str | None]] = []
            type_name_calls: list[tuple[str, str]] = []

            def __init__(
                self,
                host: str,
                port: int = 5000,
                *,
                transport: str = "tcp",
                timeout: float = 3.0,
                plc_series: PLCSeries | str = PLCSeries.QL,
                frame_type: cli.FrameType | str = cli.FrameType.FRAME_4E,
                default_target: SlmpTarget | None = None,
                monitoring_timer: int = 0x0010,
                raise_on_error: bool = True,
                trace_hook=None,
            ) -> None:
                super().__init__(
                    host,
                    port,
                    transport=transport,
                    timeout=timeout,
                    plc_series=plc_series,
                    frame_type=frame_type,
                    default_target=default_target,
                    monitoring_timer=monitoring_timer,
                    raise_on_error=raise_on_error,
                    trace_hook=trace_hook,
                )

            def connect(self) -> None:
                return None

            def close(self) -> None:
                return None

            def read_devices(self, device, points, *, bit_unit=False, series=None):  # type: ignore[override]
                resolved_series = (
                    series.value if isinstance(series, PLCSeries) else (str(series) if series is not None else None)
                )
                type(self).read_calls.append((str(device), int(points), bool(bit_unit), resolved_series))
                return [0]

            def read_type_name(self) -> TypeNameInfo:
                type(self).type_name_calls.append((self.frame_type.value, self.plc_series.value))
                raise RuntimeError("type name unsupported")

        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "other_station_check_latest.md"
            with (
                patch.object(cli, "SlmpClient", OtherStationTypeNameFailureClient),
                patch.object(cli, "_load_compatibility_policy", return_value=None),
            ):
                rc = cli.other_station_check_main(
                    [
                        "--host",
                        "192.168.250.100",
                        "--series",
                        "ql",
                        "--frame-type",
                        "3e",
                        "--target",
                        "SELF",
                        "--output",
                        str(output),
                    ]
                )
            report = output.read_text(encoding="utf-8")

        self.assertEqual(rc, 0)
        self.assertEqual(OtherStationTypeNameFailureClient.read_calls, [("D1000", 1, False, "ql")])
        self.assertEqual(OtherStationTypeNameFailureClient.type_name_calls, [("3e", "ql")])
        self.assertIn("type_name_error=type name unsupported", report)

    def test_other_station_check_main_adds_practical_note_for_ql_other_station_failures(self) -> None:
        """Test test_other_station_check_main_adds_practical_note_for_ql_other_station_failures."""

        class OtherStationTimeoutClient(SlmpClient):
            def __init__(
                self,
                host: str,
                port: int = 5000,
                *,
                transport: str = "tcp",
                timeout: float = 3.0,
                plc_series: PLCSeries | str = PLCSeries.QL,
                frame_type: cli.FrameType | str = cli.FrameType.FRAME_4E,
                default_target: SlmpTarget | None = None,
                monitoring_timer: int = 0x0010,
                raise_on_error: bool = True,
                trace_hook=None,
            ) -> None:
                super().__init__(
                    host,
                    port,
                    transport=transport,
                    timeout=timeout,
                    plc_series=plc_series,
                    frame_type=frame_type,
                    default_target=default_target,
                    monitoring_timer=monitoring_timer,
                    raise_on_error=raise_on_error,
                    trace_hook=trace_hook,
                )

            def connect(self) -> None:
                return None

            def close(self) -> None:
                return None

            def read_devices(self, device, points, *, bit_unit=False, series=None) -> NoReturn:  # type: ignore[override]
                raise TimeoutError("timed out")

        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "other_station_check_latest.md"
            with (
                patch.object(cli, "SlmpClient", OtherStationTimeoutClient),
                patch.object(cli, "_load_compatibility_policy", return_value=None),
            ):
                rc = cli.other_station_check_main(
                    [
                        "--host",
                        "192.168.250.100",
                        "--series",
                        "ql",
                        "--frame-type",
                        "3e",
                        "--target",
                        "NW1-ST1",
                        "--output",
                        str(output),
                    ]
                )
            report = output.read_text(encoding="utf-8")

        self.assertEqual(rc, 2)
        self.assertIn("Practical note:", report)

    def test_other_station_check_main_uses_compatibility_policy_order(self) -> None:
        """Test test_other_station_check_main_uses_compatibility_policy_order."""

        class PolicyOtherStationClient(SlmpClient):
            init_calls: list[tuple[str, str]] = []
            read_calls: list[tuple[str, int, bool, str | None]] = []
            type_name_calls: list[tuple[str, str]] = []

            def __init__(
                self,
                host: str,
                port: int = 5000,
                *,
                transport: str = "tcp",
                timeout: float = 3.0,
                plc_series: PLCSeries | str = PLCSeries.QL,
                frame_type: cli.FrameType | str = cli.FrameType.FRAME_4E,
                default_target: SlmpTarget | None = None,
                monitoring_timer: int = 0x0010,
                raise_on_error: bool = True,
                trace_hook=None,
            ) -> None:
                super().__init__(
                    host,
                    port,
                    transport=transport,
                    timeout=timeout,
                    plc_series=plc_series,
                    frame_type=frame_type,
                    default_target=default_target,
                    monitoring_timer=monitoring_timer,
                    raise_on_error=raise_on_error,
                    trace_hook=trace_hook,
                )
                type(self).init_calls.append((self.frame_type.value, self.plc_series.value))

            def connect(self) -> None:
                return None

            def close(self) -> None:
                return None

            def read_devices(self, device, points, *, bit_unit=False, series=None):  # type: ignore[override]
                resolved_series = (
                    series.value if isinstance(series, PLCSeries) else (str(series) if series is not None else None)
                )
                type(self).read_calls.append((str(device), int(points), bool(bit_unit), resolved_series))
                if self.frame_type.value != "4e" or resolved_series != "ql":
                    raise RuntimeError("policy should try 4e/ql first")
                return [0]

            def read_type_name(self) -> TypeNameInfo:
                type(self).type_name_calls.append((self.frame_type.value, self.plc_series.value))
                return TypeNameInfo(raw=b"\x00" * 18, model="R08CPU", model_code=0x4801)

        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "other_station_check_latest.md"
            policy_path = Path(tmp) / "compatibility_policy.json"
            policy_path.write_text(
                json.dumps({"global": {"preferred_profiles": ["4e/ql", "3e/ql", "4e/iqr", "3e/iqr"]}}),
                encoding="utf-8",
            )
            with patch.object(cli, "SlmpClient", PolicyOtherStationClient):
                rc = cli.other_station_check_main(
                    [
                        "--host",
                        "192.168.250.100",
                        "--series",
                        "ql",
                        "--frame-type",
                        "4e",
                        "--compatibility-policy",
                        str(policy_path),
                        "--target",
                        "SELF",
                        "--output",
                        str(output),
                    ]
                )
            report = output.read_text(encoding="utf-8")

        self.assertEqual(rc, 0)
        self.assertEqual(PolicyOtherStationClient.init_calls, [("4e", "ql"), ("4e", "ql")])
        self.assertEqual(PolicyOtherStationClient.read_calls, [("D1000", 1, False, "ql")])
        self.assertEqual(PolicyOtherStationClient.type_name_calls, [("4e", "ql")])
        self.assertIn("Resolved frame: 4e", report)

    def test_compatibility_probe_main_writes_json_and_markdown(self) -> None:
        """Test test_compatibility_probe_main_writes_json_and_markdown."""

        class CompatibilityProbeClient(SlmpClient):
            def __init__(
                self,
                host: str,
                port: int = 5000,
                *,
                transport: str = "tcp",
                timeout: float = 3.0,
                plc_series: PLCSeries | str = PLCSeries.QL,
                frame_type: cli.FrameType | str = cli.FrameType.FRAME_4E,
                default_target: SlmpTarget | None = None,
                monitoring_timer: int = 0x0010,
                raise_on_error: bool = True,
                trace_hook=None,
            ) -> None:
                super().__init__(
                    host,
                    port,
                    transport=transport,
                    timeout=timeout,
                    plc_series=plc_series,
                    frame_type=frame_type,
                    default_target=default_target,
                    monitoring_timer=monitoring_timer,
                    raise_on_error=raise_on_error,
                    trace_hook=trace_hook,
                )

            def connect(self) -> None:
                return None

            def close(self) -> None:
                return None

            def read_type_name(self) -> TypeNameInfo:
                return TypeNameInfo(raw=b"\x00" * 18, model="Q26UDEHCPU", model_code=0x026C)

            def read_devices(self, device, points, *, bit_unit=False, series=None):  # type: ignore[override]
                if bit_unit:
                    return [True]
                return [0]

            def read_block(self, *, word_blocks=(), bit_blocks=(), series=None, split_mixed_blocks=False):  # type: ignore[override]
                return BlockReadResult(word_blocks=[], bit_blocks=[])

        with TemporaryDirectory() as tmp:
            output_md = Path(tmp) / "compatibility_probe_latest.md"
            output_json = Path(tmp) / "compatibility_probe_latest.json"
            with patch.object(cli, "SlmpClient", CompatibilityProbeClient):
                rc = cli.compatibility_probe_main(
                    [
                        "--host",
                        "192.168.250.100",
                        "--plc-label",
                        "Q26UDEHCPU_BuiltIn",
                        "--series",
                        "ql",
                        "--frame-type",
                        "3e",
                        "--command",
                        "0101",
                        "--command",
                        "0401",
                        "--command",
                        "0406",
                        "--output-markdown",
                        str(output_md),
                        "--output-json",
                        str(output_json),
                    ]
                )
            report = output_md.read_text(encoding="utf-8")
            payload = json.loads(output_json.read_text(encoding="utf-8"))

        self.assertEqual(rc, 0)
        self.assertEqual(payload["plc_label"], "Q26UDEHCPU_BuiltIn")
        self.assertEqual(payload["selected_commands"], ["0101", "0401", "0406"])
        self.assertEqual(payload["results"][0]["frame_type"], "3e")
        self.assertEqual(payload["results"][0]["access_profile"], "ql")
        self.assertEqual(payload["results"][0]["detected_model"], "Q26UDHCPU, Q26UDEHCPU")
        self.assertIn("3e/ql 0101 Read Type Name", report)
        self.assertIn("3e/ql 0406 Block Read", report)

    def test_compatibility_probe_main_rejects_auto_series_and_frame(self) -> None:
        """Test test_compatibility_probe_main_rejects_auto_series_and_frame."""

        with self.assertRaises(SystemExit) as cm:
            cli.compatibility_probe_main(
                [
                    "--host",
                    "192.168.250.100",
                    "--series",
                    "auto",
                    "--frame-type",
                    "auto",
                ]
            )

        self.assertEqual(cm.exception.code, 2)

    def test_compatibility_matrix_render_main_renders_output(self) -> None:
        """Test test_compatibility_matrix_render_main_renders_output."""
        with TemporaryDirectory() as tmp:
            input_a = Path(tmp) / "probe_a.json"
            input_b = Path(tmp) / "probe_b.json"
            output = Path(tmp) / "PLC_COMPATIBILITY.md"
            policy_output = Path(tmp) / "compatibility_policy.json"
            input_a.write_text(
                json.dumps(
                    {
                        "plc_label": "PLC-A",
                        "results": [
                            {
                                "frame_type": "3e",
                                "access_profile": "ql",
                                "commands": [{"code": "0101", "status": "OK"}],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            input_b.write_text(
                json.dumps(
                    {
                        "plc_label": "PLC-B",
                        "results": [
                            {
                                "frame_type": "4e",
                                "access_profile": "iqr",
                                "commands": [{"code": "0101", "status": "NG"}],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            rc = cli.compatibility_matrix_render_main(
                [
                    "--input",
                    str(input_a),
                    "--input",
                    str(input_b),
                    "--omit-pending-columns",
                    "--policy-output",
                    str(policy_output),
                    "--output",
                    str(output),
                ]
            )
            content = output.read_text(encoding="utf-8")
            policy = json.loads(policy_output.read_text(encoding="utf-8"))

        self.assertEqual(rc, 0)
        self.assertIn("| PLC-A | unknown_target | YES |", content)
        self.assertIn("| PLC-B | unknown_target | NO |", content)
        self.assertNotIn("**1401**", content)
        self.assertIn("global", policy)
        self.assertIn("preferred_profiles", policy["global"])

    def test_manual_label_verification_main_requires_label_args(self) -> None:
        """Test test_manual_label_verification_main_requires_label_args."""
        with self.assertRaises(SystemExit) as ctx:
            cli.manual_label_verification_main(["--host", "192.168.250.100"])
        self.assertEqual(ctx.exception.code, 2)

    def test_manual_label_verification_main_processes_random_and_array_labels(self) -> None:
        """Test test_manual_label_verification_main_processes_random_and_array_labels."""

        class ManualLabelClient(SlmpClient):
            init_monitoring_timers: list[int] = []
            random_read_calls: list[list[str]] = []
            random_write_calls: list[list[LabelRandomWritePoint]] = []
            array_read_calls: list[list[LabelArrayReadPoint]] = []
            array_write_calls: list[list[LabelArrayWritePoint]] = []

            def __init__(
                self,
                host: str,
                port: int = 5000,
                *,
                transport: str = "tcp",
                timeout: float = 3.0,
                plc_series: PLCSeries | str = PLCSeries.QL,
                default_target: SlmpTarget | None = None,
                monitoring_timer: int = 0x0010,
                raise_on_error: bool = True,
                trace_hook=None,
            ) -> None:
                super().__init__(
                    host,
                    port,
                    transport=transport,
                    timeout=timeout,
                    plc_series=plc_series,
                    default_target=default_target,
                    monitoring_timer=monitoring_timer,
                    raise_on_error=raise_on_error,
                    trace_hook=trace_hook,
                )
                type(self).init_monitoring_timers.append(monitoring_timer)

            def connect(self) -> None:
                return None

            def close(self) -> None:
                return None

            def read_random_labels(self, labels, *, abbreviation_labels=()):  # type: ignore[override]
                type(self).random_read_calls.append(list(labels))
                return [
                    LabelRandomReadResult(
                        data_type_id=0x02,
                        spare=0,
                        read_data_length=2,
                        data=b"\x34\x12",
                    )
                    for _ in labels
                ]

            def write_random_labels(self, points, *, abbreviation_labels=()) -> None:  # type: ignore[override]
                type(self).random_write_calls.append(list(points))

            def read_array_labels(self, points, *, abbreviation_labels=()):  # type: ignore[override]
                type(self).array_read_calls.append(list(points))
                return [
                    LabelArrayReadResult(
                        data_type_id=0x02,
                        unit_specification=point.unit_specification,
                        array_data_length=point.array_data_length,
                        data=b"\x10\x00\x20\x00",
                    )
                    for point in points
                ]

            def write_array_labels(self, points, *, abbreviation_labels=()) -> None:  # type: ignore[override]
                type(self).array_write_calls.append(list(points))

        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "manual_label_verification_latest.md"
            with patch.object(cli, "SlmpClient", ManualLabelClient):
                with patch("builtins.input", side_effect=["", "Y", "", "Y"]):
                    rc = cli.manual_label_verification_main(
                        [
                            "--host",
                            "192.168.250.100",
                            "--series",
                            "iqr",
                            "--monitoring-timer",
                            "0x0020",
                            "--label-random",
                            "LabelW",
                            "--label-array",
                            "DDD[0]:1:4",
                            "--output",
                            str(output),
                        ]
                    )
            report = output.read_text(encoding="utf-8")

        self.assertEqual(rc, 0)
        self.assertEqual(ManualLabelClient.init_monitoring_timers, [0x0020])
        self.assertEqual(ManualLabelClient.random_read_calls, [["LabelW"]])
        self.assertEqual(
            ManualLabelClient.random_write_calls,
            [
                [LabelRandomWritePoint(label="LabelW", data=b"\x35\x12")],
                [LabelRandomWritePoint(label="LabelW", data=b"\x34\x12")],
            ],
        )
        self.assertEqual(ManualLabelClient.array_read_calls[0][0], LabelArrayReadPoint("DDD[0]", 1, 4))
        self.assertEqual(
            ManualLabelClient.array_write_calls,
            [
                [
                    LabelArrayWritePoint(
                        label="DDD[0]",
                        unit_specification=1,
                        array_data_length=4,
                        data=b"\x11\x00\x20\x00",
                    )
                ],
                [
                    LabelArrayWritePoint(
                        label="DDD[0]",
                        unit_specification=1,
                        array_data_length=4,
                        data=b"\x10\x00\x20\x00",
                    )
                ],
            ],
        )
        self.assertIn("# Manual Label Verification Report", report)
        self.assertIn("- Monitoring timer: 0x0020", report)
        self.assertIn("| random LabelW | OK |", report)
        self.assertIn("| array DDD[0]:1:4 | OK |", report)

    def test_pending_live_verification_main_uses_monitoring_timer_and_skips_reset(self) -> None:
        """Test test_pending_live_verification_main_uses_monitoring_timer_and_skips_reset."""

        class PendingCliClient(SlmpClient):
            init_monitoring_timers: list[int] = []
            array_read_calls: list[list[LabelArrayReadPoint]] = []
            array_write_calls: list[list[LabelArrayWritePoint]] = []
            random_read_calls: list[list[str]] = []
            random_write_calls: list[list[LabelRandomWritePoint]] = []

            def __init__(
                self,
                host: str,
                port: int = 5000,
                *,
                transport: str = "tcp",
                timeout: float = 3.0,
                plc_series: PLCSeries | str = PLCSeries.QL,
                default_target: SlmpTarget | None = None,
                monitoring_timer: int = 0x0010,
                raise_on_error: bool = True,
                trace_hook=None,
            ) -> None:
                super().__init__(
                    host,
                    port,
                    transport=transport,
                    timeout=timeout,
                    plc_series=plc_series,
                    default_target=default_target,
                    monitoring_timer=monitoring_timer,
                    raise_on_error=raise_on_error,
                    trace_hook=trace_hook,
                )
                type(self).init_monitoring_timers.append(monitoring_timer)

            def connect(self) -> None:
                return None

            def close(self) -> None:
                self._sock = None

            def request(self, command, subcommand=0x0000, data=b"", **kwargs):  # type: ignore[override]
                return SlmpResponse(
                    serial=0,
                    target=SlmpTarget(),
                    end_code=0,
                    data=b"",
                    raw=b"",
                )

            def extend_unit_read_bytes(self, head_address: int, size: int, module_no: int) -> bytes:
                return b"\xb1\xe9"

            def extend_unit_write_bytes(self, head_address: int, module_no: int, data: bytes) -> None:
                return None

            def read_array_labels(
                self,
                points,
                *,
                abbreviation_labels=(),
            ):
                type(self).array_read_calls.append(list(points))
                return [
                    LabelArrayReadResult(
                        data_type_id=0x02,
                        unit_specification=point.unit_specification,
                        array_data_length=point.array_data_length,
                        data=(
                            b"\x34\x12"
                            if point.array_data_length == 2
                            else (b"\x34\x12" * (point.array_data_length // 2))
                        ),
                    )
                    for point in points
                ]

            def write_array_labels(
                self,
                points,
                *,
                abbreviation_labels=(),
            ) -> None:
                type(self).array_write_calls.append(list(points))

            def read_random_labels(
                self,
                labels,
                *,
                abbreviation_labels=(),
            ):
                type(self).random_read_calls.append(list(labels))
                return [
                    LabelRandomReadResult(
                        data_type_id=0x02,
                        spare=0x00,
                        read_data_length=2,
                        data=b"\x34\x12",
                    )
                    for _ in labels
                ]

            def write_random_labels(
                self,
                points,
                *,
                abbreviation_labels=(),
            ) -> None:
                type(self).random_write_calls.append(list(points))

            def read_type_name(self) -> TypeNameInfo:
                return TypeNameInfo(raw=b"\x00" * 18, model="R08CPU", model_code=0x4801)

        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "pending_live_verification_latest.md"
            with patch.object(cli, "SlmpClient", PendingCliClient):
                rc = cli.pending_live_verification_main(
                    [
                        "--host",
                        "192.168.250.100",
                        "--series",
                        "iqr",
                        "--monitoring-timer",
                        "0x0020",
                        "--output",
                        str(output),
                    ]
                )
            report = output.read_text(encoding="utf-8")

        self.assertEqual(rc, 0)
        self.assertEqual(PendingCliClient.init_monitoring_timers, [0x0020])
        self.assertEqual(PendingCliClient.array_read_calls[0][0].label, "LabelW")
        self.assertEqual(PendingCliClient.array_write_calls[0][0].data, b"\x34\x12")
        self.assertEqual(PendingCliClient.random_read_calls[0], ["LabelW"])
        self.assertEqual(PendingCliClient.random_write_calls[0][0].data, b"\x34\x12")
        self.assertIn(
            "| 1006 remote reset | SKIP | excluded from live verification scope |",
            report,
        )

    def test_pending_live_verification_main_uses_custom_label_specs(self) -> None:
        """Test test_pending_live_verification_main_uses_custom_label_specs."""

        class PendingLabelClient(SlmpClient):
            array_read_calls: list[list[LabelArrayReadPoint]] = []
            random_read_calls: list[list[str]] = []

            def connect(self) -> None:
                return None

            def close(self) -> None:
                self._sock = None

            def request(self, command, subcommand=0x0000, data=b"", **kwargs):  # type: ignore[override]
                return SlmpResponse(
                    serial=0,
                    target=SlmpTarget(),
                    end_code=0,
                    data=b"",
                    raw=b"",
                )

            def read_array_labels(self, points, *, abbreviation_labels=()) -> NoReturn:
                type(self).array_read_calls.append(list(points))
                raise SlmpError("label missing")

            def read_random_labels(self, labels, *, abbreviation_labels=()) -> NoReturn:
                type(self).random_read_calls.append(list(labels))
                raise SlmpError("label missing")

            def extend_unit_read_bytes(self, head_address: int, size: int, module_no: int) -> bytes:
                return b"\x00\x00"

            def extend_unit_write_bytes(self, head_address: int, module_no: int, data: bytes) -> None:
                return None

        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "pending_live_verification_latest.md"
            with patch.object(cli, "SlmpClient", PendingLabelClient):
                rc = cli.pending_live_verification_main(
                    [
                        "--host",
                        "192.168.250.100",
                        "--series",
                        "iqr",
                        "--label-array",
                        "GGG.ZZZ.ZZZ.DDD[0]:1:20",
                        "--label-random",
                        "GGG.ZZZ.ZZZ.DDD[0]",
                        "--output",
                        str(output),
                    ]
                )
            report = output.read_text(encoding="utf-8")

        self.assertEqual(rc, 0)
        self.assertEqual(PendingLabelClient.array_read_calls[0][0].label, "GGG.ZZZ.ZZZ.DDD[0]")
        self.assertEqual(PendingLabelClient.array_read_calls[0][0].array_data_length, 20)
        self.assertEqual(PendingLabelClient.random_read_calls[0], ["GGG.ZZZ.ZZZ.DDD[0]"])
        self.assertIn(
            "| 141A label array write | SKIP | array read unavailable; no safe same-value payload |",
            report,
        )
        self.assertIn(
            "| 141B label random write | SKIP | random read unavailable; no safe same-value payload |",
            report,
        )


class TestDeviceApi(unittest.TestCase):
    """TestDeviceApi class."""

    def test_read_devices_word(self) -> None:
        """Test test_read_devices_word."""
        client = FakeClient()
        client.next_response_data = b"\x34\x12\x78\x56"
        values = client.read_devices("D100", 2, bit_unit=False, series=PLCSeries.QL)
        self.assertEqual(values, [0x1234, 0x5678])

        assert client.last_request is not None
        command, subcommand, payload, _ = client.last_request
        self.assertEqual(command, Command.DEVICE_READ)
        self.assertEqual(subcommand, 0x0000)
        self.assertEqual(payload, b"\x64\x00\x00\xa8\x02\x00")

    def test_practical_path_warning_for_lt_direct_access(self) -> None:
        """Direct LT state access must fail instead of warning."""
        client = FakeClient()
        with self.assertRaisesRegex(ValueError, "Direct bit read is not supported for LTC"):
            client.read_devices("LTC0", 1, bit_unit=True, series=PLCSeries.IQR)
        self.assertIsNone(client.last_request)

    def test_direct_bit_read_rejects_long_timer_state_devices(self) -> None:
        """Direct bit reads for LT/LST state devices must fail before transport."""
        client = FakeClient()
        with self.assertRaisesRegex(ValueError, "Direct bit read is not supported for LTC"):
            client.read_devices("LTC0", 1, bit_unit=True, series=PLCSeries.IQR)
        self.assertIsNone(client.last_request)

    def test_direct_word_read_requires_four_word_long_timer_blocks(self) -> None:
        """LTN/LSTN direct reads must use 4-word units."""
        client = FakeClient()
        with self.assertRaisesRegex(ValueError, "requires 4-word blocks"):
            client.read_devices("LTN0", 2, bit_unit=False, series=PLCSeries.IQR)
        self.assertIsNone(client.last_request)

        client.next_response_data = b"\x01\x00\x02\x00\x03\x00\x04\x00"
        out = client.read_devices("LTN0", 4, bit_unit=False, series=PLCSeries.IQR)
        self.assertEqual(out, [1, 2, 3, 4])

    def test_read_dwords_rejects_long_timer_direct_dword_path(self) -> None:
        """Helper dword reads must not use 2-word direct LT paths."""
        client = FakeClient()
        with self.assertRaisesRegex(ValueError, "requires 4-word blocks"):
            client.read_dwords("LTN0", 1, series=PLCSeries.IQR)
        self.assertIsNone(client.last_request)

    def test_temporarily_unsupported_device_error_for_g_direct_only(self) -> None:
        """Test test_temporarily_unsupported_device_error_for_g_direct_only."""
        client = FakeClient()
        client.next_response_data = b"\x11\x11"
        with self.assertRaises(SlmpUnsupportedDeviceError):
            client.read_devices("G0", 1, bit_unit=False, series=PLCSeries.IQR)

    def test_extended_device_g_read_payload_matches_capture_shape(self) -> None:
        """Test test_extended_device_g_read_payload_matches_capture_shape."""
        client = FakeClient()
        client.next_response_data = b"\x11\x11"
        ext = ExtensionSpec(
            extension_specification=0x0000,
            extension_specification_modification=0x00,
            device_modification_index=0x00,
            device_modification_flags=0x00,
            direct_memory_specification=0xFA,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SlmpPracticalPathWarning)
            out = client.read_devices_ext(r"U3E0\G10", 1, extension=ext, bit_unit=False, series=PLCSeries.IQR)
        self.assertEqual(out, [0x1111])
        command, subcommand, payload, _ = client.last_request
        self.assertEqual(command, Command.DEVICE_READ)
        self.assertEqual(subcommand, 0x0082)
        self.assertEqual(payload, b"\x00\x00\x0a\x00\x00\x00\xab\x00\x00\x00\xe0\x03\xfa\x01\x00")

    def test_extended_device_ql_g_read_payload_matches_capture_shape(self) -> None:
        """Test test_extended_device_ql_g_read_payload_matches_capture_shape."""
        client = FakeClient()
        client.next_response_data = b"\x22\x00"
        ext = ExtensionSpec(
            extension_specification=0x0000,
            extension_specification_modification=0x00,
            device_modification_index=0x00,
            device_modification_flags=0x00,
            direct_memory_specification=0xF8,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SlmpPracticalPathWarning)
            out = client.read_devices_ext(r"U01\G22", 1, extension=ext, bit_unit=False, series=PLCSeries.QL)
        self.assertEqual(out, [0x0022])
        command, subcommand, payload, _ = client.last_request
        self.assertEqual(command, Command.DEVICE_READ)
        self.assertEqual(subcommand, 0x0080)
        self.assertEqual(payload, b"\x00\x00\x16\x00\x00\xab\x00\x00\x01\x00\xf8\x01\x00")

    def test_s_device_code_is_rejected(self) -> None:
        """Test test_s_device_code_is_rejected."""
        client = FakeClient()
        with self.assertRaisesRegex(ValueError, "Unknown SLMP device code 'S'"):
            parse_device("S0")
        with self.assertRaisesRegex(ValueError, "Unknown SLMP device code 'S'"):
            client.read_devices("S0", 1, bit_unit=True, series=PLCSeries.IQR)
        with self.assertRaisesRegex(ValueError, "Unknown SLMP device code 'S'"):
            client.write_devices("S0", [True], bit_unit=True, series=PLCSeries.IQR)
        with self.assertRaisesRegex(ValueError, "Unknown SLMP device code 'S'"):
            client.read_block(word_blocks=(), bit_blocks=[("S0", 1)], series=PLCSeries.IQR)

    def test_temporarily_unsupported_device_error_for_hg(self) -> None:
        """Test test_temporarily_unsupported_device_error_for_hg."""
        client = FakeClient()
        ext = ExtensionSpec(
            extension_specification=0x0000,
            extension_specification_modification=0x00,
            device_modification_index=0x00,
            device_modification_flags=0x00,
            direct_memory_specification=0xFA,
        )
        with self.assertRaises(SlmpUnsupportedDeviceError):
            client.read_devices("HG0", 1, bit_unit=False, series=PLCSeries.IQR)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SlmpPracticalPathWarning)
            client.write_devices_ext(r"U3E0\HG20", [0x0032], extension=ext, bit_unit=False, series=PLCSeries.IQR)
        command, subcommand, payload, _ = client.last_request
        self.assertEqual(command, Command.DEVICE_WRITE)
        self.assertEqual(subcommand, 0x0082)
        self.assertEqual(payload, b"\x00\x00\x14\x00\x00\x00\x2e\x00\x00\x00\xe0\x03\xfa\x01\x00\x32\x00")

    def test_register_monitor_devices_ext_accepts_u3e0_qualified_device(self) -> None:
        """Test test_register_monitor_devices_ext_accepts_u3e0_qualified_device."""
        client = FakeClient()
        ext = ExtensionSpec(
            extension_specification=0x0000,
            extension_specification_modification=0x00,
            device_modification_index=0x00,
            device_modification_flags=0x00,
            direct_memory_specification=0xFA,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SlmpPracticalPathWarning)
            client.register_monitor_devices_ext(word_devices=[(r"U3E0\G10", ext)], series=PLCSeries.IQR)
        command, subcommand, payload, _ = client.last_request
        self.assertEqual(command, Command.DEVICE_ENTRY_MONITOR)
        self.assertEqual(subcommand, 0x0082)
        self.assertEqual(payload, b"\x01\x00\x00\x00\x0a\x00\x00\x00\xab\x00\x00\x00\xe0\x03\xfa")

    def test_boundary_warning_for_multi_point_r_family_access(self) -> None:
        """Test test_boundary_warning_for_multi_point_r_family_access."""
        client = FakeClient()
        client.next_response_data = b"\x00\x00\x00\x00"
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            client.read_devices("ZR163839", 2, bit_unit=False, series=PLCSeries.IQR)
        self.assertTrue(any(item.category is SlmpBoundaryBehaviorWarning for item in caught))

    def test_boundary_warning_for_odd_lz_write(self) -> None:
        """Test test_boundary_warning_for_odd_lz_write."""
        client = FakeClient()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            client.write_devices("LZ1", [0], bit_unit=False, series=PLCSeries.IQR)
        self.assertTrue(any(item.category is SlmpBoundaryBehaviorWarning for item in caught))

    def test_r_device_fixed_upper_limit(self) -> None:
        """Test test_r_device_fixed_upper_limit."""
        client = FakeClient()
        with self.assertRaises(ValueError):
            client.read_devices("R32768", 1, bit_unit=False, series=PLCSeries.IQR)
        with self.assertRaises(ValueError):
            client.write_devices("R32768", [1], bit_unit=False, series=PLCSeries.IQR)

    def test_write_random_bits(self) -> None:
        """Test test_write_random_bits."""
        client = FakeClient()
        client.write_random_bits({"M10": True, "Y20": False}, series=PLCSeries.QL)
        command, subcommand, payload, _ = client.last_request
        self.assertEqual(command, Command.DEVICE_WRITE_RANDOM)
        self.assertEqual(subcommand, 0x0001)
        self.assertEqual(payload[0], 2)

        client.write_random_bits({"M10": True, "Y20": False}, series=PLCSeries.IQR)
        command, subcommand, payload, _ = client.last_request
        self.assertEqual(command, Command.DEVICE_WRITE_RANDOM)
        self.assertEqual(subcommand, 0x0003)
        self.assertEqual(payload[0], 2)
        # iQ-R/iQ-L random bit write state is 2 bytes per point (ON=01 00, OFF=00 00)
        self.assertIn(b"\x90\x00\x01\x00", payload)
        self.assertTrue(payload.endswith(b"\x9d\x00\x00\x00"))

    def test_manual_write_helpers_use_lt_lst_special_paths(self) -> None:
        """Test test_manual_write_helpers_use_lt_lst_special_paths."""

        class ManualProbeClient(FakeClient):
            def read_ltc_states(self, *, head_no=0, points=1, series=None):  # type: ignore[override]
                self.last_request = ("read_ltc_states", head_no, points, series)
                return [True]

            def read_lts_states(self, *, head_no=0, points=1, series=None):  # type: ignore[override]
                self.last_request = ("read_lts_states", head_no, points, series)
                return [False]

            def read_lstc_states(self, *, head_no=0, points=1, series=None):  # type: ignore[override]
                self.last_request = ("read_lstc_states", head_no, points, series)
                return [True]

            def read_lsts_states(self, *, head_no=0, points=1, series=None):  # type: ignore[override]
                self.last_request = ("read_lsts_states", head_no, points, series)
                return [False]

        client = ManualProbeClient()
        self.assertTrue(
            cli._read_manual_row_value(
                client,
                cli.DeviceMatrixRow("LTC", "LTC10", "bit", "", "NG", "SKIP", ""),
                series="iqr",
            )
        )
        self.assertEqual(client.last_request, ("read_ltc_states", 10, 1, "iqr"))
        self.assertFalse(
            cli._read_manual_row_value(
                client,
                cli.DeviceMatrixRow("LTS", "LTS10", "bit", "", "NG", "SKIP", ""),
                series="iqr",
            )
        )
        self.assertEqual(client.last_request, ("read_lts_states", 10, 1, "iqr"))
        self.assertTrue(
            cli._read_manual_row_value(
                client,
                cli.DeviceMatrixRow("LSTC", "LSTC10", "bit", "", "NG", "SKIP", ""),
                series="iqr",
            )
        )
        self.assertEqual(client.last_request, ("read_lstc_states", 10, 1, "iqr"))
        self.assertFalse(
            cli._read_manual_row_value(
                client,
                cli.DeviceMatrixRow("LSTS", "LSTS10", "bit", "", "NG", "SKIP", ""),
                series="iqr",
            )
        )
        self.assertEqual(client.last_request, ("read_lsts_states", 10, 1, "iqr"))

        cli._write_manual_row_value(
            client,
            cli.DeviceMatrixRow("LTC", "LTC10", "bit", "", "NG", "SKIP", ""),
            True,
            series="iqr",
        )
        command, subcommand, payload, _ = client.last_request
        self.assertEqual(command, Command.DEVICE_WRITE_RANDOM)
        self.assertEqual(subcommand, 0x0003)
        self.assertEqual(payload[0], 1)
        self.assertEqual(payload[1:4], b"\x0a\x00\x00")
        self.assertEqual(payload[-2:], b"\x01\x00")

    def test_memory_read_words(self) -> None:
        """Test test_memory_read_words."""
        client = FakeClient()
        client.next_response_data = b"\x11\x11\x22\x22"
        out = client.memory_read_words(0x1234, 2)
        self.assertEqual(out, [0x1111, 0x2222])
        command, subcommand, payload, _ = client.last_request
        self.assertEqual(command, Command.MEMORY_READ)
        self.assertEqual(subcommand, 0x0000)
        self.assertEqual(payload, b"\x34\x12\x00\x00\x02\x00")

    def test_extend_unit_write_bytes(self) -> None:
        """Test test_extend_unit_write_bytes."""
        client = FakeClient()
        client.extend_unit_write_bytes(0x10, 0x0003, b"\x01\x02\x03\x04")
        command, subcommand, payload, _ = client.last_request
        self.assertEqual(command, Command.EXTEND_UNIT_WRITE)
        self.assertEqual(subcommand, 0x0000)
        self.assertEqual(payload, b"\x10\x00\x00\x00\x04\x00\x03\x00\x01\x02\x03\x04")

    def test_extend_unit_word_helpers(self) -> None:
        """Test test_extend_unit_word_helpers."""
        client = FakeClient()
        client.next_response_data = b"\x11\x11\x22\x22"
        out = client.extend_unit_read_words(0x20, 2, 0x03E0)
        self.assertEqual(out, [0x1111, 0x2222])
        command, subcommand, payload, _ = client.last_request
        self.assertEqual(command, Command.EXTEND_UNIT_READ)
        self.assertEqual(subcommand, 0x0000)
        self.assertEqual(payload, b"\x20\x00\x00\x00\x04\x00\xe0\x03")

        client.extend_unit_write_words(0x20, 0x03E0, [0x3333, 0x4444])
        command, subcommand, payload, _ = client.last_request
        self.assertEqual(command, Command.EXTEND_UNIT_WRITE)
        self.assertEqual(subcommand, 0x0000)
        self.assertEqual(payload, b"\x20\x00\x00\x00\x04\x00\xe0\x03\x33\x33\x44\x44")

        client.next_response_data = b"\x55\x55"
        self.assertEqual(client.extend_unit_read_word(0x30, 0x03E0), 0x5555)
        command, subcommand, payload, _ = client.last_request
        self.assertEqual(command, Command.EXTEND_UNIT_READ)
        self.assertEqual(payload, b"\x30\x00\x00\x00\x02\x00\xe0\x03")

        client.next_response_data = b"\x78\x56\x34\x12"
        self.assertEqual(client.extend_unit_read_dword(0x34, 0x03E0), 0x12345678)
        command, subcommand, payload, _ = client.last_request
        self.assertEqual(command, Command.EXTEND_UNIT_READ)
        self.assertEqual(payload, b"\x34\x00\x00\x00\x04\x00\xe0\x03")

        client.extend_unit_write_word(0x30, 0x03E0, 0x5555)
        command, subcommand, payload, _ = client.last_request
        self.assertEqual(command, Command.EXTEND_UNIT_WRITE)
        self.assertEqual(payload, b"\x30\x00\x00\x00\x02\x00\xe0\x03\x55\x55")

        client.extend_unit_write_dword(0x34, 0x03E0, 0x12345678)
        command, subcommand, payload, _ = client.last_request
        self.assertEqual(command, Command.EXTEND_UNIT_WRITE)
        self.assertEqual(payload, b"\x34\x00\x00\x00\x04\x00\xe0\x03\x78\x56\x34\x12")

    def test_cpu_buffer_word_helpers_default_to_03e0(self) -> None:
        """Test test_cpu_buffer_word_helpers_default_to_03e0."""
        client = FakeClient()
        client.next_response_data = b"\x01\x48"
        out = client.cpu_buffer_read_words(0x04, 1)
        self.assertEqual(out, [0x4801])
        command, subcommand, payload, _ = client.last_request
        self.assertEqual(command, Command.EXTEND_UNIT_READ)
        self.assertEqual(subcommand, 0x0000)
        self.assertEqual(payload, b"\x04\x00\x00\x00\x02\x00\xe0\x03")

        client.cpu_buffer_write_words(0x04, [0x4801])
        command, subcommand, payload, _ = client.last_request
        self.assertEqual(command, Command.EXTEND_UNIT_WRITE)
        self.assertEqual(subcommand, 0x0000)
        self.assertEqual(payload, b"\x04\x00\x00\x00\x02\x00\xe0\x03\x01\x48")

        client.next_response_data = b"\x01\x48"
        self.assertEqual(client.cpu_buffer_read_word(0x04), 0x4801)
        command, subcommand, payload, _ = client.last_request
        self.assertEqual(command, Command.EXTEND_UNIT_READ)
        self.assertEqual(payload, b"\x04\x00\x00\x00\x02\x00\xe0\x03")

        client.next_response_data = b"\xb1\xe9\xaf\x95"
        self.assertEqual(client.cpu_buffer_read_dword(0x00), 0x95AFE9B1)
        command, subcommand, payload, _ = client.last_request
        self.assertEqual(command, Command.EXTEND_UNIT_READ)
        self.assertEqual(payload, b"\x00\x00\x00\x00\x04\x00\xe0\x03")

        client.cpu_buffer_write_word(0x04, 0x4801)
        command, subcommand, payload, _ = client.last_request
        self.assertEqual(command, Command.EXTEND_UNIT_WRITE)
        self.assertEqual(payload, b"\x04\x00\x00\x00\x02\x00\xe0\x03\x01\x48")

        client.cpu_buffer_write_dword(0x00, 0x95AFE9B1)
        command, subcommand, payload, _ = client.last_request
        self.assertEqual(command, Command.EXTEND_UNIT_WRITE)
        self.assertEqual(payload, b"\x00\x00\x00\x00\x04\x00\xe0\x03\xb1\xe9\xaf\x95")

    def test_remote_run(self) -> None:
        """Test test_remote_run."""
        client = FakeClient()
        client.remote_run(force=False, clear_mode=2)
        command, subcommand, payload, _ = client.last_request
        self.assertEqual(command, Command.REMOTE_RUN)
        self.assertEqual(subcommand, 0x0000)
        self.assertEqual(payload, b"\x01\x00\x02\x00")

    def test_self_test_loopback(self) -> None:
        """Test test_self_test_loopback."""
        client = FakeClient()
        client.next_response_data = b"\x05\x00ABCDE"
        out = client.self_test_loopback("ABCDE")
        self.assertEqual(out, b"ABCDE")
        command, subcommand, payload, _ = client.last_request
        self.assertEqual(command, Command.SELF_TEST)
        self.assertEqual(subcommand, 0x0000)
        self.assertEqual(payload, b"\x05\x00ABCDE")

    def test_remote_reset_uses_no_response_mode_by_default(self) -> None:
        """Test test_remote_reset_uses_no_response_mode_by_default."""
        client = FakeClient()
        client.remote_reset()
        expected_kwargs = {"serial": None, "target": None, "monitoring_timer": None}
        self.assertEqual(client.last_no_response, (int(Command.REMOTE_RESET), 0x0000, b"", expected_kwargs))

        client.remote_reset()
        self.assertEqual(client.last_no_response, (int(Command.REMOTE_RESET), 0x0000, b"", expected_kwargs))

    def test_read_devices_ext(self) -> None:
        """Test test_read_devices_ext."""
        client = FakeClient()
        client.next_response_data = b"\x11\x11"
        ext = ExtensionSpec(
            extension_specification=0x0001,
            extension_specification_modification=0x00,
            device_modification_index=0x00,
            device_modification_flags=0x00,
            direct_memory_specification=0xF9,
        )
        out = client.read_devices_ext("W100", 1, extension=ext, bit_unit=False, series=PLCSeries.QL)
        self.assertEqual(out, [0x1111])
        command, subcommand, payload, _ = client.last_request
        self.assertEqual(command, Command.DEVICE_READ)
        self.assertEqual(subcommand, 0x0080)
        # Link direct format: 00 00 | dev_no(3) | dev_code(1) | 00 00 | j_net(1) | 00 | f9 | pts(2)
        self.assertEqual(payload, b"\x00\x00\x00\x01\x00\xb4\x00\x00\x01\x00\xf9\x01\x00")

    def test_write_block_mixed_split(self) -> None:
        """Test test_write_block_mixed_split."""
        client = FakeClient()
        client.write_block(
            word_blocks=[("D100", [0x1111])],
            bit_blocks=[("M200", [0x0001])],
            series=PLCSeries.QL,
            split_mixed_blocks=True,
        )
        self.assertEqual(len(client.requests), 2)
        self.assertEqual(client.requests[0][0], Command.DEVICE_WRITE_BLOCK)
        self.assertEqual(client.requests[1][0], Command.DEVICE_WRITE_BLOCK)

    def test_write_block_default_keeps_mixed_request(self) -> None:
        """Test test_write_block_default_keeps_mixed_request."""
        client = FakeClient()
        client.write_block(
            word_blocks=[("D100", [0x1111])],
            bit_blocks=[("M200", [0x0001])],
            series=PLCSeries.QL,
        )
        self.assertEqual(len(client.requests), 1)
        self.assertEqual(client.requests[0][0], Command.DEVICE_WRITE_BLOCK)

    def test_write_block_retry_mixed_on_c05b_splits_after_failed_combined_request(self) -> None:
        """Test test_write_block_retry_mixed_on_c05b_splits_after_failed_combined_request."""
        client = FakeClient()
        client.response_queue = [(0xC05B, b""), (0x0000, b""), (0x0000, b"")]
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            client.write_block(
                word_blocks=[("D100", [0x1111])],
                bit_blocks=[("M200", [0x0001])],
                series=PLCSeries.IQR,
                retry_mixed_on_error=True,
            )
        self.assertEqual(len(client.requests), 3)
        self.assertEqual([request[0] for request in client.requests], [Command.DEVICE_WRITE_BLOCK] * 3)
        self.assertEqual([request[2][:2] for request in client.requests], [b"\x01\x01", b"\x01\x00", b"\x00\x01"])
        self.assertTrue(all(request[3]["raise_on_error"] is False for request in client.requests))
        self.assertTrue(
            any(isinstance(item.message, SlmpPracticalPathWarning) and "0xC05B" in str(item.message) for item in caught)
        )

    def test_write_block_retry_mixed_on_c056_splits_after_failed_combined_request(self) -> None:
        """Test test_write_block_retry_mixed_on_c056_splits_after_failed_combined_request."""
        client = FakeClient()
        client.response_queue = [(0xC056, b""), (0x0000, b""), (0x0000, b"")]
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            client.write_block(
                word_blocks=[("D100", [0x1111])],
                bit_blocks=[("M200", [0x0001])],
                series=PLCSeries.QL,
                retry_mixed_on_error=True,
            )
        self.assertEqual(len(client.requests), 3)
        self.assertEqual([request[0] for request in client.requests], [Command.DEVICE_WRITE_BLOCK] * 3)
        self.assertEqual([request[2][:2] for request in client.requests], [b"\x01\x01", b"\x01\x00", b"\x00\x01"])
        self.assertTrue(all(request[3]["raise_on_error"] is False for request in client.requests))
        self.assertTrue(
            any(isinstance(item.message, SlmpPracticalPathWarning) and "0xC056" in str(item.message) for item in caught)
        )

    def test_write_block_retry_mixed_on_c061_splits_after_failed_combined_request(self) -> None:
        """Test test_write_block_retry_mixed_on_c061_splits_after_failed_combined_request."""
        client = FakeClient()
        client.response_queue = [(0xC061, b""), (0x0000, b""), (0x0000, b"")]
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            client.write_block(
                word_blocks=[("D100", [0x1111])],
                bit_blocks=[("M200", [0x0001])],
                series=PLCSeries.QL,
                retry_mixed_on_error=True,
            )
        self.assertEqual(len(client.requests), 3)
        self.assertEqual([request[0] for request in client.requests], [Command.DEVICE_WRITE_BLOCK] * 3)
        self.assertEqual([request[2][:2] for request in client.requests], [b"\x01\x01", b"\x01\x00", b"\x00\x01"])
        self.assertTrue(all(request[3]["raise_on_error"] is False for request in client.requests))
        self.assertTrue(
            any(isinstance(item.message, SlmpPracticalPathWarning) and "0xC061" in str(item.message) for item in caught)
        )

    def test_write_block_retry_mixed_on_unknown_end_code_does_not_split(self) -> None:
        """Test test_write_block_retry_mixed_on_unknown_end_code_does_not_split."""
        client = FakeClient()
        client.response_queue = [(0xC059, b"")]
        with self.assertRaises(SlmpError) as ctx:
            client.write_block(
                word_blocks=[("D100", [0x1111])],
                bit_blocks=[("M200", [0x0001])],
                series=PLCSeries.IQR,
                retry_mixed_on_error=True,
            )
        self.assertEqual(ctx.exception.end_code, 0xC059)
        self.assertEqual(len(client.requests), 1)

    def test_g_hg_extended_device_coverage_main_read_only(self) -> None:
        """Test test_g_hg_extended_device_coverage_main_read_only."""

        class CoverageClient(SlmpClient):
            read_calls: list[tuple[str, int, int]] = []
            write_calls: list[tuple[str, list[int], int]] = []

            def connect(self) -> None:
                return None

            def close(self) -> None:
                self._sock = None

            def read_type_name(self) -> TypeNameInfo:
                return TypeNameInfo(raw=b"\x00" * 18, model="R120PCPU", model_code=0x4801)

            def read_devices_ext(self, device, points, *, extension, bit_unit=False, series=None):  # type: ignore[override]
                type(self).read_calls.append((str(device), int(points), int(extension.direct_memory_specification)))
                return [index for index in range(int(points))]

            def write_devices_ext(self, device, values, *, extension, bit_unit=False, series=None) -> None:  # type: ignore[override]
                type(self).write_calls.append(
                    (str(device), [int(value) for value in values], int(extension.direct_memory_specification))
                )

        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "g_hg_extended_device_coverage_latest.md"
            with patch.object(cli, "SlmpClient", CoverageClient):
                rc = cli.g_hg_extended_device_coverage_main(
                    [
                        "--host",
                        "192.168.250.100",
                        "--series",
                        "iqr",
                        "--device",
                        r"U3E0\G10",
                        "--device",
                        r"U3E0\HG20",
                        "--points",
                        "1",
                        "--points",
                        "4",
                        "--output",
                        str(output),
                    ]
                )
            report = output.read_text(encoding="utf-8")

        self.assertEqual(rc, 0)
        self.assertEqual(CoverageClient.write_calls, [])
        self.assertEqual(
            CoverageClient.read_calls,
            [
                (r"U3E0\G10", 1, 0xFA),
                (r"U3E0\G10", 4, 0xFA),
                (r"U3E0\HG20", 1, 0xFA),
                (r"U3E0\HG20", 4, 0xFA),
            ],
        )
        self.assertIn("# G/HG Extended Device Coverage Report", report)
        self.assertIn("- Mode: read_only", report)
        self.assertIn(r"| U3E0\G10 points=1 direct=0xFA | OK |", report)

    def test_g_hg_extended_device_coverage_main_write_check_restores_values(self) -> None:
        """Test test_g_hg_extended_device_coverage_main_write_check_restores_values."""

        class CoverageWriteClient(SlmpClient):
            memory: dict[str, list[int]] = {r"U01\G22": [0x1000, 0x1001]}
            write_calls: list[tuple[str, list[int], int]] = []

            def connect(self) -> None:
                return None

            def close(self) -> None:
                self._sock = None

            def read_type_name(self) -> TypeNameInfo:
                return TypeNameInfo(raw=b"\x00" * 18, model="FX5UC-32MT/D", model_code=0x0000)

            def read_devices_ext(self, device, points, *, extension, bit_unit=False, series=None):  # type: ignore[override]
                values = list(type(self).memory[str(device)])
                return values[: int(points)]

            def write_devices_ext(self, device, values, *, extension, bit_unit=False, series=None) -> None:  # type: ignore[override]
                normalized = [int(value) & 0xFFFF for value in values]
                type(self).write_calls.append((str(device), normalized, int(extension.direct_memory_specification)))
                type(self).memory[str(device)] = list(normalized)

        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "g_hg_extended_device_coverage_latest.md"
            with patch.object(cli, "SlmpClient", CoverageWriteClient):
                rc = cli.g_hg_extended_device_coverage_main(
                    [
                        "--host",
                        "192.168.250.100",
                        "--series",
                        "ql",
                        "--device",
                        r"U01\G22",
                        "--points",
                        "2",
                        "--write-check",
                        "--preferred-write-base",
                        "0x0020",
                        "--output",
                        str(output),
                    ]
                )
            report = output.read_text(encoding="utf-8")

        self.assertEqual(rc, 0)
        self.assertEqual(CoverageWriteClient.memory[r"U01\G22"], [0x1000, 0x1001])
        self.assertEqual(
            CoverageWriteClient.write_calls,
            [
                (r"U01\G22", [0x0020, 0x0021], 0xF8),
                (r"U01\G22", [0x1000, 0x1001], 0xF8),
            ],
        )
        self.assertIn("- Mode: write_check", report)
        self.assertIn("restore=ok", report)

    def test_g_hg_extended_device_coverage_main_handles_multiple_transports_and_targets(self) -> None:
        """Test test_g_hg_extended_device_coverage_main_handles_multiple_transports_and_targets."""

        class CoverageMatrixClient(SlmpClient):
            init_calls: list[tuple[str, int, int, int]] = []
            read_calls: list[tuple[str, str, int, int, int]] = []

            def __init__(
                self,
                host: str,
                port: int = 5000,
                *,
                transport: str = "tcp",
                timeout: float = 3.0,
                plc_series: PLCSeries | str = PLCSeries.QL,
                frame_type: cli.FrameType | str = cli.FrameType.FRAME_4E,
                default_target: SlmpTarget | None = None,
                monitoring_timer: int = 0x0010,
                raise_on_error: bool = True,
                trace_hook=None,
            ) -> None:
                super().__init__(
                    host,
                    port,
                    transport=transport,
                    timeout=timeout,
                    plc_series=plc_series,
                    frame_type=frame_type,
                    default_target=default_target,
                    monitoring_timer=monitoring_timer,
                    raise_on_error=raise_on_error,
                    trace_hook=trace_hook,
                )
                assert default_target is not None
                type(self).init_calls.append(
                    (
                        self.transport,
                        int(default_target.network),
                        int(default_target.station),
                        int(default_target.module_io),
                    )
                )

            def connect(self) -> None:
                return None

            def close(self) -> None:
                self._sock = None

            def read_type_name(self) -> TypeNameInfo:
                return TypeNameInfo(raw=b"\x00" * 18, model="R120PCPU", model_code=0x4804)

            def read_devices_ext(self, device, points, *, extension, bit_unit=False, series=None):  # type: ignore[override]
                assert self.default_target is not None
                type(self).read_calls.append(
                    (
                        self.transport,
                        str(device),
                        int(points),
                        int(self.default_target.network),
                        int(self.default_target.station),
                    )
                )
                return [0] * int(points)

        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "g_hg_extended_device_coverage_latest.md"
            with patch.object(cli, "SlmpClient", CoverageMatrixClient):
                rc = cli.g_hg_extended_device_coverage_main(
                    [
                        "--host",
                        "192.168.250.100",
                        "--series",
                        "iqr",
                        "--transport",
                        "tcp",
                        "--transport",
                        "udp",
                        "--target",
                        "SELF",
                        "--target",
                        "NW1-ST2",
                        "--device",
                        r"U3E0\G10",
                        "--points",
                        "1",
                        "--output",
                        str(output),
                    ]
                )
            report = output.read_text(encoding="utf-8")

        self.assertEqual(rc, 0)
        self.assertEqual(
            CoverageMatrixClient.init_calls,
            [
                ("tcp", 0x00, 0xFF, 0x03FF),
                ("tcp", 0x01, 0x02, 0x03FF),
                ("udp", 0x00, 0xFF, 0x03FF),
                ("udp", 0x01, 0x02, 0x03FF),
            ],
        )
        self.assertEqual(
            CoverageMatrixClient.read_calls,
            [
                ("tcp", r"U3E0\G10", 1, 0x00, 0xFF),
                ("tcp", r"U3E0\G10", 1, 0x01, 0x02),
                ("udp", r"U3E0\G10", 1, 0x00, 0xFF),
                ("udp", r"U3E0\G10", 1, 0x01, 0x02),
            ],
        )
        self.assertIn("- Transports: tcp, udp", report)
        self.assertIn("- Targets: SELF(", report)
        self.assertIn("NW1-ST2(", report)
        self.assertIn(r"| tcp SELF U3E0\G10 points=1 direct=0xFA | OK |", report)
        self.assertIn(r"| udp NW1-ST2 U3E0\G10 points=1 direct=0xFA | OK |", report)

    def test_g_hg_extended_device_coverage_main_type_name_failure_is_nonfatal(self) -> None:
        """Test test_g_hg_extended_device_coverage_main_type_name_failure_is_nonfatal."""

        class CoverageTypeNameFailureClient(SlmpClient):
            read_calls: list[tuple[str, int, int]] = []

            def connect(self) -> None:
                return None

            def close(self) -> None:
                self._sock = None

            def read_type_name(self) -> TypeNameInfo:
                raise RuntimeError("type name unsupported")

            def read_devices_ext(self, device, points, *, extension, bit_unit=False, series=None):  # type: ignore[override]
                type(self).read_calls.append((str(device), int(points), int(extension.direct_memory_specification)))
                return [0] * int(points)

        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "g_hg_extended_device_coverage_latest.md"
            with patch.object(cli, "SlmpClient", CoverageTypeNameFailureClient):
                rc = cli.g_hg_extended_device_coverage_main(
                    [
                        "--host",
                        "192.168.250.100",
                        "--series",
                        "ql",
                        "--device",
                        r"U01\G22",
                        "--points",
                        "1",
                        "--output",
                        str(output),
                    ]
                )
            report = output.read_text(encoding="utf-8")

        self.assertEqual(rc, 0)
        self.assertEqual(CoverageTypeNameFailureClient.read_calls, [(r"U01\G22", 1, 0xF8)])
        self.assertIn("# G/HG Extended Device Coverage Report", report)

    def test_build_regression_steps_includes_local_checks_and_help_smoke(self) -> None:
        """Test test_build_regression_steps_includes_local_checks_and_help_smoke."""
        steps = cli._build_regression_steps(
            python_executable="python",
            include_unit_tests=True,
            include_ruff=True,
            include_mypy=True,
            include_cli_help=True,
            include_live_connection_check=False,
            host=None,
            port=1025,
            transport="tcp",
            series=None,
        )

        self.assertEqual(steps[0].name, "unit_tests")
        self.assertEqual(steps[1].name, "ruff")
        self.assertEqual(steps[2].name, "mypy")
        self.assertTrue(any(step.name == "cli_help:slmp_connection_check.py" for step in steps))
        self.assertTrue(any(step.name == "cli_help:slmp_g_hg_extended_device_coverage.py" for step in steps))

    def test_regression_suite_main_runs_local_steps_and_writes_report(self) -> None:
        """Test test_regression_suite_main_runs_local_steps_and_writes_report."""
        executed: list[tuple[str, ...]] = []

        def fake_run(command, *, cwd, capture_output, text, check):  # type: ignore[no-untyped-def]
            self.assertTrue(capture_output)
            self.assertTrue(text)
            self.assertFalse(check)
            self.assertIsInstance(cwd, str)
            command_tuple = tuple(command)
            executed.append(command_tuple)
            return CompletedProcess(command, 0, stdout="ok\n", stderr="")

        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "regression_suite_latest.md"
            with patch.object(cli.subprocess, "run", side_effect=fake_run):
                rc = cli.regression_suite_main(
                    [
                        "--python",
                        "python",
                        "--output",
                        str(output),
                    ]
                )
            report = output.read_text(encoding="utf-8")

        self.assertEqual(rc, 0)
        self.assertEqual(executed[0], ("python", "-m", "unittest", "discover", "-s", "tests", "-v"))
        self.assertEqual(executed[1], ("python", "-m", "ruff", "check", "slmp", "tests", "scripts"))
        self.assertEqual(executed[2], ("python", "-m", "mypy", "slmp", "scripts"))
        self.assertIn("# Regression Suite Report", report)
        self.assertIn("| unit_tests | PASS |", report)
        self.assertIn("cli_help:slmp_connection_check.py", report)

    def test_regression_suite_main_requires_host_and_series_for_live_check(self) -> None:
        """Test test_regression_suite_main_requires_host_and_series_for_live_check."""
        with self.assertRaises(SystemExit) as ctx:
            cli.regression_suite_main(["--include-live-connection-check"])
        self.assertEqual(ctx.exception.code, 2)

    def test_read_long_timer_decode(self) -> None:
        """Test test_read_long_timer_decode."""
        client = FakeClient()
        # 2 timer points * 4 words:
        # point0: current=0x00011234, status=0x0003 (contact+coil ON)
        # point1: current=0x0002ABCD, status=0x0002 (contact ON, coil OFF)
        client.next_response_data = b"\x34\x12\x01\x00\x03\x00\x00\x00" + b"\xcd\xab\x02\x00\x02\x00\x00\x00"
        out = client.read_long_timer(head_no=10, points=2, series=PLCSeries.IQR)
        self.assertEqual(len(out), 2)
        self.assertIsInstance(out[0], LongTimerResult)
        self.assertEqual(out[0].device, "LTN10")
        self.assertEqual(out[0].current_value, 0x00011234)
        self.assertTrue(out[0].contact)
        self.assertTrue(out[0].coil)
        self.assertEqual(out[1].device, "LTN11")
        self.assertEqual(out[1].current_value, 0x0002ABCD)
        self.assertTrue(out[1].contact)
        self.assertFalse(out[1].coil)
        command, subcommand, payload, _ = client.last_request
        self.assertEqual(command, Command.DEVICE_READ)
        self.assertEqual(subcommand, 0x0002)
        self.assertEqual(payload[-2:], b"\x08\x00")

    def test_read_long_retentive_timer_decode(self) -> None:
        """Test test_read_long_retentive_timer_decode."""
        client = FakeClient()
        client.next_response_data = b"\x11\x11\x22\x22\x01\x00\x00\x00"
        out = client.read_long_retentive_timer(head_no=0, points=1, series=PLCSeries.IQR)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].device, "LSTN0")
        self.assertEqual(out[0].current_value, 0x22221111)
        self.assertFalse(out[0].contact)
        self.assertTrue(out[0].coil)
        command, subcommand, payload, _ = client.last_request
        self.assertEqual(command, Command.DEVICE_READ)
        self.assertEqual(subcommand, 0x0002)
        self.assertEqual(payload[-2:], b"\x04\x00")

    def test_long_timer_state_aliases(self) -> None:
        """Test test_long_timer_state_aliases."""
        client = FakeClient()
        client.next_response_data = b"\x34\x12\x01\x00\x03\x00\x00\x00" + b"\xcd\xab\x02\x00\x02\x00\x00\x00"
        self.assertEqual(client.read_ltc_states(head_no=10, points=2, series=PLCSeries.IQR), [True, False])
        client.next_response_data = b"\x34\x12\x01\x00\x03\x00\x00\x00" + b"\xcd\xab\x02\x00\x02\x00\x00\x00"
        self.assertEqual(client.read_lts_states(head_no=10, points=2, series=PLCSeries.IQR), [True, True])

        client.next_response_data = b"\x11\x11\x22\x22\x01\x00\x00\x00" + b"\x11\x11\x22\x22\x02\x00\x00\x00"
        self.assertEqual(client.read_lstc_states(head_no=0, points=2, series=PLCSeries.IQR), [True, False])
        client.next_response_data = b"\x11\x11\x22\x22\x01\x00\x00\x00" + b"\x11\x11\x22\x22\x02\x00\x00\x00"
        self.assertEqual(client.read_lsts_states(head_no=0, points=2, series=PLCSeries.IQR), [False, True])

    def test_read_long_timer_validation(self) -> None:
        """Test test_read_long_timer_validation."""
        client = FakeClient()
        with self.assertRaises(ValueError):
            client.read_long_timer(head_no=-1, points=1)
        with self.assertRaises(ValueError):
            client.read_long_timer(head_no=0, points=0)

    def test_label_payload_builders(self) -> None:
        """Test test_label_payload_builders."""
        p041a = SlmpClient.build_array_label_read_payload(
            [LabelArrayReadPoint(label="LabelW", unit_specification=1, array_data_length=2)],
            abbreviation_labels=["Typ1"],
        )
        self.assertEqual(
            p041a,
            b"\x01\x00\x01\x00"
            + b"\x04\x00T\x00y\x00p\x001\x00"
            + b"\x06\x00L\x00a\x00b\x00e\x00l\x00W\x00"
            + b"\x01\x00\x02\x00",
        )

        p141a = SlmpClient.build_array_label_write_payload(
            [LabelArrayWritePoint(label="LabelW", unit_specification=1, array_data_length=2, data=b"\x31\x00")]
        )
        self.assertEqual(
            p141a,
            b"\x01\x00\x00\x00" + b"\x06\x00L\x00a\x00b\x00e\x00l\x00W\x00" + b"\x01\x00\x02\x00\x31\x00",
        )

        p041c = SlmpClient.build_label_read_random_payload(["LabelB", "LabelW"])
        self.assertEqual(
            p041c,
            b"\x02\x00\x00\x00" + b"\x06\x00L\x00a\x00b\x00e\x00l\x00B\x00" + b"\x06\x00L\x00a\x00b\x00e\x00l\x00W\x00",
        )

        p141b = SlmpClient.build_label_write_random_payload([LabelRandomWritePoint(label="LabelW", data=b"\x31\x00")])
        self.assertEqual(
            p141b,
            b"\x01\x00\x00\x00" + b"\x06\x00L\x00a\x00b\x00e\x00l\x00W\x00" + b"\x02\x00\x31\x00",
        )

    def test_label_response_parsers(self) -> None:
        """Test test_label_response_parsers."""
        array_resp = b"\x02\x00" + b"\x02\x01\x02\x00\x44\x00" + b"\x01\x00\x01\x00\x01\x00"
        parsed_array = SlmpClient.parse_array_label_read_response(array_resp, expected_points=2)
        self.assertEqual(len(parsed_array), 2)
        self.assertIsInstance(parsed_array[0], LabelArrayReadResult)
        self.assertEqual(parsed_array[0].data_type_id, 0x02)
        self.assertEqual(parsed_array[0].unit_specification, 0x01)
        self.assertEqual(parsed_array[0].data, b"\x44\x00")
        self.assertEqual(parsed_array[1].unit_specification, 0x00)
        self.assertEqual(parsed_array[1].data, b"\x01\x00")

        random_resp = b"\x02\x00" + b"\x01\x00\x02\x00\x01\x00" + b"\x02\x00\x02\x00\x31\x00"
        parsed_random = SlmpClient.parse_label_read_random_response(random_resp, expected_points=2)
        self.assertEqual(len(parsed_random), 2)
        self.assertIsInstance(parsed_random[0], LabelRandomReadResult)
        self.assertEqual(parsed_random[0].data_type_id, 0x01)
        self.assertEqual(parsed_random[0].read_data_length, 2)
        self.assertEqual(parsed_random[0].data, b"\x01\x00")
        self.assertEqual(parsed_random[1].data_type_id, 0x02)
        self.assertEqual(parsed_random[1].data, b"\x31\x00")

    def test_label_typed_methods_issue_requests(self) -> None:
        """Test test_label_typed_methods_issue_requests."""
        client = FakeClient()
        client.next_response_data = b"\x01\x00\x02\x01\x02\x00\x44\x00"
        out = client.read_array_labels([LabelArrayReadPoint(label="LabelW", unit_specification=1, array_data_length=2)])
        self.assertEqual(out[0].data, b"\x44\x00")
        command, subcommand, payload, _ = client.last_request
        self.assertEqual(command, Command.LABEL_ARRAY_READ)
        self.assertEqual(subcommand, 0x0000)
        self.assertEqual(payload[:4], b"\x01\x00\x00\x00")

        client.write_array_labels(
            [LabelArrayWritePoint(label="LabelW", unit_specification=1, array_data_length=2, data=b"\x31\x00")]
        )
        command, subcommand, payload, _ = client.last_request
        self.assertEqual(command, Command.LABEL_ARRAY_WRITE)
        self.assertEqual(subcommand, 0x0000)
        self.assertTrue(payload.endswith(b"\x31\x00"))

        client.next_response_data = b"\x01\x00\x02\x00\x02\x00\x44\x00"
        out2 = client.read_random_labels(["LabelW"])
        self.assertEqual(out2[0].data, b"\x44\x00")
        command, subcommand, payload, _ = client.last_request
        self.assertEqual(command, Command.LABEL_READ_RANDOM)
        self.assertEqual(subcommand, 0x0000)
        self.assertEqual(payload[:4], b"\x01\x00\x00\x00")

        client.write_random_labels([LabelRandomWritePoint(label="LabelW", data=b"\x31\x00")])
        command, subcommand, payload, _ = client.last_request
        self.assertEqual(command, Command.LABEL_WRITE_RANDOM)
        self.assertEqual(subcommand, 0x0000)
        self.assertTrue(payload.endswith(b"\x02\x00\x31\x00"))

    def test_read_random_returns_typed_result(self) -> None:
        """Test test_read_random_returns_typed_result."""
        client = FakeClient()
        client.next_response_data = b"\x34\x12\x78\x56\xbc\x9a\x00\x00"
        out = client.read_random(word_devices=["D100", "D101"], dword_devices=["D200"], series=PLCSeries.IQR)
        self.assertIsInstance(out, RandomReadResult)
        self.assertEqual(out.word["D100"], 0x1234)
        self.assertEqual(out.word["D101"], 0x5678)
        self.assertEqual(out.dword["D200"], 0x00009ABC)

    def test_read_random_rejects_lcs_lcc(self) -> None:
        """Read Random must reject long counter state devices."""
        client = FakeClient()
        with self.assertRaisesRegex(ValueError, "Read Random \\(0x0403\\) does not support LCS/LCC"):
            client.read_random(word_devices=["LCS10"], series=PLCSeries.IQR)
        self.assertIsNone(client.last_request)

    def test_run_monitor_cycle_returns_typed_result(self) -> None:
        """Test test_run_monitor_cycle_returns_typed_result."""
        client = FakeClient()
        client.next_response_data = b"\x11\x11\x22\x22\x33\x33\x44\x44"
        out = client.run_monitor_cycle(word_points=2, dword_points=1)
        self.assertIsInstance(out, MonitorResult)
        self.assertEqual(out.word, [0x1111, 0x2222])
        self.assertEqual(out.dword, [0x44443333])

    def test_read_block_returns_typed_result(self) -> None:
        """Test test_read_block_returns_typed_result."""
        client = FakeClient()
        client.next_response_data = b"\x34\x12\x10\x00"
        out = client.read_block(
            word_blocks=[("D100", 1)],
            bit_blocks=[("M200", 1)],
            series=PLCSeries.IQR,
            split_mixed_blocks=False,
        )
        self.assertIsInstance(out, BlockReadResult)
        self.assertEqual(out.word_blocks[0].device, "D100")
        self.assertEqual(out.word_blocks[0].values, [0x1234])
        self.assertEqual(out.bit_blocks[0].device, "M200")
        self.assertEqual(out.bit_blocks[0].values, [0x0010])

    def test_read_block_multi_point_bit_values_are_packed_words(self) -> None:
        """Test test_read_block_multi_point_bit_values_are_packed_words."""
        client = FakeClient()
        client.next_response_data = b"\x05\x00\x01\x00\x01\x00\x01\x00"
        out = client.read_block(
            word_blocks=(),
            bit_blocks=[("M1000", 4)],
            series=PLCSeries.IQR,
        )
        self.assertEqual(out.bit_blocks[0].device, "M1000")
        self.assertEqual(out.bit_blocks[0].values, [0x0005, 0x0001, 0x0001, 0x0001])

    def test_read_block_rejects_lcs_lcc(self) -> None:
        """Read Block must reject long counter state devices."""
        client = FakeClient()
        with self.assertRaisesRegex(ValueError, "Read Block \\(0x0406\\) does not support LCS/LCC"):
            client.read_block(bit_blocks=[("LCS10", 1)], series=PLCSeries.IQR)
        self.assertIsNone(client.last_request)

    def test_write_block_multi_point_bit_values_are_packed_words(self) -> None:
        """Test test_write_block_multi_point_bit_values_are_packed_words."""
        client = FakeClient()
        client.write_block(
            word_blocks=(),
            bit_blocks=[("M1000", [0x0005, 0x0001])],
            series=PLCSeries.IQR,
        )
        command, subcommand, payload, _ = client.last_request
        self.assertEqual(command, Command.DEVICE_WRITE_BLOCK)
        self.assertEqual(subcommand, 0x0002)
        self.assertEqual(
            payload,
            b"\x00\x01" + encode_device_spec("M1000", series=PLCSeries.IQR) + b"\x02\x00" + b"\x05\x00\x01\x00",
        )

    def test_write_block_rejects_lcs_lcc(self) -> None:
        """Write Block must reject long counter state devices."""
        client = FakeClient()
        with self.assertRaisesRegex(ValueError, "Write Block \\(0x1406\\) does not support LCS/LCC"):
            client.write_block(bit_blocks=[("LCC10", [1])], series=PLCSeries.IQR)
        self.assertIsNone(client.last_request)

    def test_register_monitor_devices_rejects_lcs_lcc(self) -> None:
        """Monitor register must reject long counter state devices."""
        client = FakeClient()
        with self.assertRaisesRegex(ValueError, "Entry Monitor Device \\(0x0801\\) does not support LCS/LCC"):
            client.register_monitor_devices(word_devices=["LCS10"], series=PLCSeries.IQR)
        self.assertIsNone(client.last_request)

    def test_read_type_name_returns_typed_result(self) -> None:
        """Test test_read_type_name_returns_typed_result."""
        client = FakeClient()
        client.next_response_data = b"R08CPU".ljust(16, b" ") + b"\x01\x48"
        out = client.read_type_name()
        self.assertIsInstance(out, TypeNameInfo)
        self.assertEqual(out.model, "R08CPU")
        self.assertEqual(out.model_code, 0x4801)


if __name__ == "__main__":
    unittest.main()
