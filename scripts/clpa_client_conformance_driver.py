#!/usr/bin/env python
"""SLMP クライアント適合試験ドライバ (plc-comm-slmp-python 用).

CLPA SLMP コンフォーマンステストツール (SLMP_ClientTest_JPN.exe) に対して、
被試験クライアント = plc-comm-slmp-python から試験パターンの要求コマンドを発行する。

使い方:
    python client_conformance_driver.py                       # ツール既定 (TCP 127.0.0.1:61442) に接続し REPL
    python client_conformance_driver.py --transport udp       # UDP 61443
    python client_conformance_driver.py --profile melsec:qcpu:qj71e71-100 # 3E フレーム (既定 melsec:iq-r = 4E)
    python client_conformance_driver.py --host 127.0.0.1 --port 5010 --run-all   # モックサーバーでリハーサル

REPL コマンド:
    list                 項目一覧と既定パラメータ
    run <id> [k=v ...]   項目を実行 (例: run 1 device=W100 points=1)
    reconnect            接続を張り直す (セッションリセット)
    quit                 終了

注意: ツールの操作ガイド (BAP-C3011-001) に従い監視タイマは 0000h 固定。
各項目の要求内容はツール GUI の「詳細設定/パラメータ設定」に表示されるパターンに
合わせて k=v で上書きすること。
"""

from __future__ import annotations

import argparse
import shlex
import sys
from dataclasses import dataclass, field
from typing import Any, Callable

from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from slmp.client import SlmpClient  # noqa: E402
from slmp.errors import SlmpError  # noqa: E402


def _int(value: str) -> int:
    return int(value, 0)


def _values(value: str) -> list[int]:
    return [int(v, 0) for v in value.split(",") if v]


@dataclass
class Item:
    item_id: str
    command: str
    name: str
    run: Callable[[SlmpClient, dict[str, str]], Any]
    defaults: dict[str, str] = field(default_factory=dict)


def _pairs(value: str) -> list[tuple[str, int]]:
    """"W100:1,W200:2" -> [("W100", 1), ("W200", 2)]"""
    out: list[tuple[str, int]] = []
    for part in value.split(","):
        if not part:
            continue
        dev, _, num = part.partition(":")
        out.append((dev, int(num, 0)))
    return out


def _block_writes(value: str) -> list[tuple[str, list[int]]]:
    """"W100:1;2;3,W200:4" -> [("W100", [1, 2, 3]), ("W200", [4])]"""
    out: list[tuple[str, list[int]]] = []
    for part in value.split(","):
        if not part:
            continue
        dev, _, nums = part.partition(":")
        out.append((dev, [int(v, 0) for v in nums.split(";") if v]))
    return out


def _password(cli: SlmpClient, params: dict[str, str]) -> str:
    value = params.get("password", "auto")
    if value != "auto":
        return value
    series = str(getattr(cli, "plc_series", "")).lower()
    return "TESTPW" if "iq" in series else "TEST"


ITEMS: list[Item] = [
    Item("1", "0401", "一括読出し(ワード)", lambda c, p: c.read_devices(p["device"], _int(p["points"])),
         {"device": "W100", "points": "1"}),
    Item("2", "0401", "一括読出し(ビット)", lambda c, p: c.read_devices(p["device"], _int(p["points"]), bit_unit=True),
         {"device": "M100", "points": "16"}),
    Item("3", "1401", "一括書込み(ワード)", lambda c, p: c.write_devices(p["device"], _values(p["values"])),
         {"device": "W1110", "values": "0x1102"}),
    Item("4", "1401", "一括書込み(ビット)", lambda c, p: c.write_devices(p["device"], _values(p["values"]), bit_unit=True),
         {"device": "M100", "values": "1,0,1"}),
    Item("5", "0403", "ランダム読出し", lambda c, p: c.read_random(
            word_devices=[d for d in p["word_devices"].split(",") if d],
            dword_devices=[d for d in p.get("dword_devices", "").split(",") if d]),
         {"word_devices": "D0,W100", "dword_devices": "D10"}),
    Item("6", "1402", "ランダム書込み(ワード)", lambda c, p: c.write_random_words(word_values=_pairs(p["word_values"])),
         {"word_values": "D0:0x1102,W100:0x0022"}),
    Item("7", "1402", "ランダム書込み(ビット)", lambda c, p: c.write_random_bits(_pairs(p["bit_values"])),
         {"bit_values": "M100:1,M200:0"}),
    Item("8", "0801", "モニタ登録", lambda c, p: c.register_monitor_devices(
            word_devices=[d for d in p["word_devices"].split(",") if d]),
         {"word_devices": "D0,W100"}),
    Item("9", "0802", "モニタ", lambda c, p: c.run_monitor_cycle(
            word_points=_int(p["word_points"]), dword_points=_int(p.get("dword_points", "0"))),
         {"word_points": "2", "dword_points": "0"}),
    Item("10", "0406", "複数ブロック一括読出し", lambda c, p: c.read_block(word_blocks=_pairs(p["word_blocks"])),
         {"word_blocks": "W100:2,D0:2"}),
    Item("11", "1406", "複数ブロック一括書込み", lambda c, p: c.write_block(word_blocks=_block_writes(p["word_blocks"])),
         {"word_blocks": "W100:0x1102;0x0022,D0:0x0001"}),
    Item("12", "0613", "メモリ読出し", lambda c, p: c.memory_read_words(_int(p["address"]), _int(p["length"])),
         {"address": "0x0000", "length": "2"}),
    Item("13", "1613", "メモリ書込み", lambda c, p: c.memory_write_words(_int(p["address"]), _values(p["values"])),
         {"address": "0x0000", "values": "0x1102"}),
    Item("14", "0601", "拡張ユニット読出し", lambda c, p: c.extend_unit_read_words(
            _int(p["address"]), _int(p["length"]), _int(p["module"])),
         {"address": "0x0000", "length": "2", "module": "0x0000"}),
    Item("15", "1601", "拡張ユニット書込み", lambda c, p: c.extend_unit_write_words(
            _int(p["address"]), _int(p["module"]), _values(p["values"])),
         {"address": "0x0000", "module": "0x0000", "values": "0x1102"}),
    # ラッチクリアは STOP 中のみ実行可能なため、STOP の後に実行する順にしている
    Item("16", "1001", "リモートRUN", lambda c, p: c.remote_run(force=p.get("force", "0") == "1"),
         {"force": "0"}),
    Item("17", "1003", "リモートPAUSE", lambda c, p: c.remote_pause(), {}),
    Item("18", "1002", "リモートSTOP", lambda c, p: c.remote_stop(), {}),
    Item("19", "1005", "ラッチクリア", lambda c, p: c.remote_latch_clear(), {}),
    Item("20", "1006", "リモートリセット", lambda c, p: c.remote_reset(), {}),
    Item("21", "0101", "プロセッサタイプ読出し", lambda c, p: c.read_type_name(), {}),
    Item("22", "0619", "折返しテスト", lambda c, p: c.self_test_loopback(p["data"]),
         {"data": "ABCDE"}),
    Item("23", "1617", "エラーコード初期化", lambda c, p: c.clear_error(), {}),
    # リモートパスワード長は系列依存: iQ-R=6〜32 バイト / Q・L=4 バイト固定
    Item("24", "1631", "リモートパスワードロック",
         lambda c, p: c.remote_password_lock(_password(c, p)), {"password": "auto"}),
    Item("25", "1630", "リモートパスワードアンロック",
         lambda c, p: c.remote_password_unlock(_password(c, p)), {"password": "auto"}),
]

ITEM_MAP = {item.item_id: item for item in ITEMS}


def show_items() -> None:
    print(f"{'id':>3}  {'cmd':<5} {'項目':<24} 既定パラメータ")
    for item in ITEMS:
        params = " ".join(f"{k}={v}" for k, v in item.defaults.items())
        print(f"{item.item_id:>3}  {item.command:<5} {item.name:<24} {params}")


def run_item(cli: SlmpClient, item: Item, overrides: dict[str, str]) -> bool:
    params = dict(item.defaults)
    params.update(overrides)
    shown = " ".join(f"{k}={v}" for k, v in params.items())
    print(f"--- [{item.item_id}] {item.name} (cmd {item.command}) {shown}")
    try:
        result = item.run(cli, params)
    except SlmpError as exc:
        print(f"    NG: {exc}")
        return False
    except Exception as exc:  # noqa: BLE001 - 試験ドライバなので全て表示する
        print(f"    NG (driver error): {exc!r}")
        return False
    if result is None:
        print("    OK (終了コード 0000h)")
    else:
        print(f"    OK: {result}")
    return True


def make_client(args: argparse.Namespace) -> SlmpClient:
    port = args.port
    if port is None:
        port = 61442 if args.transport == "tcp" else 61443
    cli = SlmpClient(
        args.host,
        port=port,
        transport=args.transport,
        plc_profile=args.profile,
        strict_profile=False,
        timeout=args.timeout,
        monitoring_timer=args.timer,
    )
    cli.connect()
    print(
        f"connected: {args.transport} {args.host}:{port} "
        f"profile={args.profile} frame={cli.frame_type} timer=0x{args.timer:04X}"
    )
    return cli


def main() -> int:
    parser = argparse.ArgumentParser(description="SLMP client conformance test driver")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=None, help="既定: TCP=61442 / UDP=61443 (ツール固定ポート)")
    parser.add_argument("--transport", choices=["tcp", "udp"], default="tcp")
    parser.add_argument("--profile", default="melsec:iq-r",
                        help="plc_profile (フレーム形式を決める): melsec:iq-r=4E / melsec:qcpu:qj71e71-100=3E")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--timer", type=lambda v: int(v, 0), default=0x0000,
                        help="監視タイマ (ガイド指定により既定 0000h)")
    parser.add_argument("--run-all", action="store_true", help="全項目を既定パラメータで連続実行 (リハーサル用)")
    args = parser.parse_args()

    cli = make_client(args)
    try:
        if args.run_all:
            results = [run_item(cli, item, {}) for item in ITEMS]
            ok = sum(results)
            print(f"=== {ok}/{len(results)} OK ===")
            return 0 if ok == len(results) else 1

        show_items()
        print("コマンド: list / run <id> [k=v ...] / reconnect / quit")
        while True:
            try:
                line = input("> ").strip()
            except EOFError:
                break
            if not line:
                continue
            words = shlex.split(line)
            cmd = words[0].lower()
            if cmd in {"quit", "exit", "q"}:
                break
            if cmd == "list":
                show_items()
                continue
            if cmd == "reconnect":
                cli.close()
                cli = make_client(args)
                continue
            if cmd == "run" and len(words) >= 2:
                item = ITEM_MAP.get(words[1])
                if item is None:
                    print(f"unknown item id: {words[1]}")
                    continue
                overrides = dict(w.split("=", 1) for w in words[2:] if "=" in w)
                run_item(cli, item, overrides)
                continue
            print("usage: list / run <id> [k=v ...] / reconnect / quit")
    finally:
        cli.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
