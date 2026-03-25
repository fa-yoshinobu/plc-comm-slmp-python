#!/usr/bin/env python
"""SLMP Ultra-Stable TUI Monitor.

Ensures no-scroll performance, maintains status messages, and shows PLC Model/Run-State.
Accurately detects bit-unit devices using library metadata.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any, cast

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slmp import DEVICE_CODES, AsyncSlmpClient, SlmpError, parse_device
from slmp.constants import DeviceUnit

# ANSI Escape Codes
HOME = "\033[H"
HIDE_CUR = "\033[?25l"
SHOW_CUR = "\033[?25h"
CLR_EOS = "\033[J"
INV = "\033[7m"
RST = "\033[0m"
GRN = "\033[92m"
YLW = "\033[93m"
BLU = "\033[94m"
RED = "\033[91m"
BOLD = "\033[1m"
BG_GRN = "\033[42m\033[30m"
BG_RED = "\033[41m\033[30m"


class UltraStableMonitor:
    """Ultra-stable TUI monitor for SLMP."""

    def __init__(self) -> None:
        """Initialize the monitor."""
        self.host = "127.0.0.1"
        self.port = 5000
        self.series = "iqr"
        self.targets: list[dict[str, Any]] = []
        self.prev_values: dict[str, Any] = {}
        self.status = "INIT"
        self.last_error = ""
        self.mode_desc = "Normal"
        self.current_page = 0
        self.plc_model = "Unknown"
        self.plc_running = False

        # Heartbeat / Watchdog
        self.heartbeat = False
        self.last_hb_val: bool | None = None
        self.last_hb_time = 0.0

        self.input_active = False
        self.temp_msg = ""
        self.msg_expiry = 0.0
        self.last_size = (0, 0)

    def show_msg(self, msg: str, duration: float = 3.0) -> None:
        """Show a temporary message in the status line."""
        self.temp_msg = msg
        self.msg_expiry = time.time() + duration

    def get_terminal_dimensions(self) -> tuple[int, int]:
        """Get current terminal columns and lines."""
        try:
            size = os.get_terminal_size()
            return size.columns, size.lines
        except OSError:
            return 80, 24

    def render(self) -> None:
        """Render the UI to terminal."""
        if self.input_active:
            return
        cols, rows = self.get_terminal_dimensions()
        if (cols, rows) != self.last_size:
            sys.stdout.write("\033[2J")
            self.last_size = (cols, rows)

        data_area_height = max(1, rows - 8)

        all_lines = []
        for target in self.targets:
            values = target.get("last_values", [0] * target["count"])
            for i, val in enumerate(values):
                addr = f"{target['device'].code}{target['device'].number + i}"
                changed = self.prev_values.get(addr) is not None and self.prev_values.get(addr) != val
                self.prev_values[addr] = val
                color = YLW if changed else ""
                if target["is_bit"]:
                    state = "ON " if val else "OFF"
                    line = f"{addr:<15} | {'-':<10} | {'-':<10} | {state}"
                else:
                    h_val = f"0x{val:04X}"
                    b_val = format(val, "016b")
                    b_fmt = " ".join([b_val[k : k + 4] for k in range(0, 16, 4)])
                    line = f"{addr:<15} | {val:<10} | {h_val:<10} | {b_fmt}"
                all_lines.append((color, line))

        total_pages = (len(all_lines) + data_area_height - 1) // data_area_height if all_lines else 1
        self.current_page = max(0, min(self.current_page, total_pages - 1))
        page_items = all_lines[self.current_page * data_area_height : (self.current_page + 1) * data_area_height]

        buf = []
        # 1. Header Line
        run_l = " RUN  " if self.plc_running else " STOP "
        run_c = BG_GRN if self.plc_running else BG_RED
        hb_icon = "*" if self.heartbeat else "."

        # [SLMP] [ONLINE] | R08CPU * [ RUN ] 127.0.0.1:5000
        h_l = f" SLMP | {self.status} | {self.plc_model} {hb_icon} "
        h_r = f"[{run_l}]"
        h_mid = f" {self.host}:{self.port}"
        sys.stdout.write(
            HOME
            + HIDE_CUR
            + INV
            + h_l
            + RST
            + run_c
            + h_r
            + RST
            + INV
            + h_mid.ljust(cols - len(h_l) - len(h_r))
            + RST
            + "\n"
        )

        # 2. Sub-info
        sub_info = (
            f" {datetime.now().strftime('%H:%M:%S')} | Page {self.current_page + 1}/{total_pages} | {self.mode_desc}"
        )
        buf.append(f"{BLU}{sub_info[: cols - 1]:<{cols - 1}}{RST}")
        buf.append("-" * (cols - 1))

        # 3. Table Header
        t_head = f"{'DEVICE':<15} | {'DEC':<10} | {'HEX':<10} | {'BINARY'}"
        buf.append(f"{BOLD}{t_head[: cols - 1]:<{cols - 1}}{RST}")
        buf.append("-" * (cols - 1))

        # 4. Data Area
        for i in range(data_area_height):
            if i < len(page_items):
                color, content = page_items[i]
                buf.append(f"{color}{content[: cols - 1]:<{cols - 1}}{RST}")
            elif i == 0 and not all_lines:
                buf.append(f" {'(Press a to add devices)':<{cols - 2}}")
            else:
                buf.append(" " * (cols - 1))

        # 5. Footer (Notify/Error + Menu)
        buf.append("-" * (cols - 1))
        if time.time() < self.msg_expiry:
            msg = f" NOTIFY: {self.temp_msg}"
            color = GRN if "Success" in self.temp_msg else YLW
        elif self.last_error:
            msg = f" ERROR: {self.last_error[: cols - 10]}"
            color = RED
        else:
            msg = ""  # Keep line empty but existing to avoid scroll
            color = RST
        buf.append(f"{color}{msg[: cols - 1]:<{cols - 1}}{RST}")

        menu = " [a] Add  [c] Clear  [h] Host  [s] Sim  [[] Prev  []] Next  [q] Quit"
        buf.append(f"{INV}{menu[: cols - 1]:<{cols - 1}}{RST}")

        sys.stdout.write("\n".join(buf) + CLR_EOS)
        sys.stdout.flush()

    async def poll_plc(self) -> None:
        """Poll the PLC in background."""
        while True:
            if not self.targets:
                self.plc_model = "Unknown"
                self.plc_running = False
                self.status = "IDLE"
                self.render()
                await asyncio.sleep(0.5)
                continue
            try:
                async with AsyncSlmpClient(self.host, self.port, plc_series=self.series, timeout=1.5) as cli:
                    self.status = "ONLINE"
                    self.last_error = ""
                    type_info = await cli.read_type_name()
                    self.plc_model = type_info.model
                    while True:
                        if not self.targets:
                            break
                        tasks = [cli.read_devices(t["device"], t["count"], bit_unit=t["is_bit"]) for t in self.targets]
                        tasks.append(cli.read_devices("SM403", 1, bit_unit=True))
                        tasks.append(cli.read_devices("SM412", 1, bit_unit=True))
                        try:
                            results = await asyncio.gather(*tasks)
                            hb_list = cast(list[bool], results.pop())
                            run_list = cast(list[bool], results.pop())
                            hb_val, run_flag = hb_list[0], run_list[0]
                            now = time.time()
                            if hb_val != self.last_hb_val or run_flag:
                                self.plc_running = True
                                self.last_hb_time = now
                            elif now - self.last_hb_time > 2.5:
                                self.plc_running = False
                            self.last_hb_val, self.heartbeat = hb_val, hb_val
                            for target, res in zip(self.targets, results, strict=False):
                                target["last_values"] = res
                        except SlmpError as se:
                            self.last_error = f"SLMP: 0x{se.end_code:04X}"
                        except Exception as e:
                            self.last_error = f"{e}"
                        self.render()
                        await asyncio.sleep(0.2)
            except Exception as e:
                self.status = "OFFLINE"
                self.plc_running = False
                self.last_error = f"{e}"
                self.render()
                await asyncio.sleep(2)

    async def handle_input(self) -> None:
        """Handle keyboard input."""
        if sys.platform == "win32":
            import msvcrt

            while True:
                if msvcrt.kbhit():
                    char = msvcrt.getch()
                    if char in (b"\x00", b"\xe0"):
                        msvcrt.getch()
                        continue
                    key = char.decode(errors="ignore").lower()
                    if key == "q":
                        sys.stdout.write(SHOW_CUR + "\nGoodbye!\n")
                        os._exit(0)
                    elif key == "a":
                        await self.prompt_action("ADD DEVICE", self.add_device)
                    elif key == "c":
                        self.targets = []
                        self.prev_values = {}
                        self.current_page = 0
                        self.show_msg("Success: Cleared list")
                    elif key == "h":
                        await self.prompt_action("CHANGE HOST IP", self.change_host)
                    elif key == "s":
                        await self.prompt_sim()
                    elif key == "[":
                        self.current_page -= 1
                    elif key == "]":
                        self.current_page += 1
                    self.render()
                await asyncio.sleep(0.05)
        else:
            # Non-Windows input handling (basic)
            while True:
                await asyncio.sleep(1.0)

    async def prompt_action(self, title: str, callback: Callable[[str], Any]) -> None:
        """Prompt user for input and call callback."""
        self.input_active = True
        _, rows = self.get_terminal_dimensions()
        sys.stdout.write(f"\033[{rows};0H\033[2K{INV} {title}: {RST} ")
        sys.stdout.write(SHOW_CUR)
        sys.stdout.flush()
        loop = asyncio.get_running_loop()
        val = (await loop.run_in_executor(None, sys.stdin.readline)).strip()
        self.input_active = False
        sys.stdout.write(HIDE_CUR)
        if val:
            try:
                res = callback(val)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                self.last_error = f"Error: {e}"
        self.render()

    def add_device(self, val: str) -> None:
        """Add a device or range to the monitor."""
        if "-" in val:
            start, end = val.split("-")
            ref = parse_device(start)
            count = int(end) - ref.number + 1
            is_bit = DEVICE_CODES[ref.code].unit == DeviceUnit.BIT
            self.targets.append({"device": ref, "count": count, "is_bit": is_bit})
        else:
            ref = parse_device(val)
            is_bit = DEVICE_CODES[ref.code].unit == DeviceUnit.BIT
            self.targets.append({"device": ref, "count": 1, "is_bit": is_bit})
        self.show_msg(f"Success: Added {val}")

    def change_host(self, val: str) -> None:
        """Change the target PLC host IP."""
        self.host = val
        self.targets = []
        self.mode_desc = "Normal"
        self.show_msg("Success: Host changed")

    async def prompt_sim(self) -> None:
        """Prompt for GX Simulator 3 connection."""
        self.input_active = True
        _, rows = self.get_terminal_dimensions()
        sys.stdout.write(f"\033[{rows};0H\033[2K{INV} GX Sim (SysNo PLCNo): {RST} ")
        sys.stdout.write(SHOW_CUR)
        sys.stdout.flush()
        loop = asyncio.get_running_loop()
        val = (await loop.run_in_executor(None, sys.stdin.readline)).strip()
        self.input_active = False
        sys.stdout.write(HIDE_CUR)
        try:
            parts = val.split()
            s_n = parts[0] if len(parts) > 0 else "1"
            p_n = parts[1] if len(parts) > 1 else "1"
            self.port = int(f"55{int(s_n)}{int(p_n)}")
            self.host = "127.0.0.1"
            self.mode_desc = f"GX Sim {s_n}-{p_n}"
            self.targets = []
            self.current_page = 0
            self.show_msg("Success: Sim Connected")
        except Exception as e:
            self.last_error = f"Sim Error: {e}"
        self.render()


async def main() -> None:
    """Main entry point for interactive monitor."""
    monitor = UltraStableMonitor()
    sys.stdout.write("\033[2J\033[H" + HIDE_CUR)
    sys.stdout.flush()
    monitor.render()
    await asyncio.gather(monitor.poll_plc(), monitor.handle_input())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.stdout.write(SHOW_CUR + "\n")
