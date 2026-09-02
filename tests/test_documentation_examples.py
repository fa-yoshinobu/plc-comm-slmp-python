from __future__ import annotations

import ast
import asyncio
import textwrap
from pathlib import Path
from types import SimpleNamespace
from typing import Any

USAGE_GUIDE = Path(__file__).parents[1] / "docsrc" / "user" / "USAGE_GUIDE.md"
GETTING_STARTED = Path(__file__).parents[1] / "docsrc" / "user" / "GETTING_STARTED.md"


def _python_blocks(markdown: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] | None = None
    for line in markdown.splitlines():
        stripped = line.strip()
        if current is None and stripped.startswith("```python"):
            current = []
        elif current is not None and stripped == "```":
            blocks.append(textwrap.dedent("\n".join(current)))
            current = None
        elif current is not None:
            current.append(line)
    assert current is None, "unclosed Python fence"
    return blocks


def _block_containing(blocks: list[str], needle: str) -> str:
    matches = [block for block in blocks if needle in block]
    assert len(matches) == 1, f"expected one Python block containing {needle!r}"
    return matches[0]


class _OutcomeUnknownError(Exception):
    pass


class _ReadbackError(Exception):
    pass


def _without_imports_and_runner(block: str) -> ast.Module:
    tree = ast.parse(block)
    tree.body = [
        node
        for node in tree.body
        if not isinstance(node, (ast.Import, ast.ImportFrom))
        and not (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute)
            and isinstance(node.value.func.value, ast.Name)
            and node.value.func.value.id == "asyncio"
            and node.value.func.attr == "run"
        )
    ]
    ast.fix_missing_locations(tree)
    return tree


def _run_sync_example(block: str, client: Any) -> None:
    namespace = {
        "SlmpClient": lambda *_args, **_kwargs: client,
        "SlmpOutcomeUnknownError": _OutcomeUnknownError,
        "SlmpTarget": lambda **kwargs: SimpleNamespace(**kwargs),
    }
    exec(compile(_without_imports_and_runner(block), "USAGE_GUIDE.md", "exec"), namespace)


async def _run_async_example(block: str, client: Any) -> None:
    async def open_and_connect(_options: Any) -> Any:
        return client

    namespace = {
        "SlmpConnectionOptions": lambda **kwargs: SimpleNamespace(**kwargs),
        "SlmpTarget": lambda **kwargs: SimpleNamespace(**kwargs),
        "open_and_connect": open_and_connect,
    }
    exec(compile(_without_imports_and_runner(block), "USAGE_GUIDE.md", "exec"), namespace)
    await namespace["main"]()


async def _run_async_helper_example(block: str, client: Any, helpers: dict[str, Any]) -> None:
    async def open_and_connect(_options: Any) -> Any:
        return client

    namespace = {
        "SlmpConnectionOptions": lambda **kwargs: SimpleNamespace(**kwargs),
        "SlmpTarget": lambda **kwargs: SimpleNamespace(**kwargs),
        "open_and_connect": open_and_connect,
        **helpers,
    }
    exec(compile(_without_imports_and_runner(block), "documentation example", "exec"), namespace)
    await namespace["main"]()


class _SyncExtendedClient:
    def __init__(self, *, fail_write_at: int | None = None, fail_read_at: int | None = None) -> None:
        self.fail_write_at = fail_write_at
        self.fail_read_at = fail_read_at
        self.read_count = 0
        self.writes: list[tuple[str, list[int | bool], bool]] = []

    def __enter__(self) -> _SyncExtendedClient:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read_devices_extended(self, device: str, points: int, *, bit_unit: bool) -> list[int] | list[bool]:
        self.read_count += 1
        if self.read_count == self.fail_read_at:
            raise _ReadbackError
        if device == "J1\\X11":
            return [False]
        return list(range(10, 10 + points))

    def write_devices_extended(self, device: str, values: list[int | bool], *, bit_unit: bool) -> None:
        self.writes.append((device, list(values), bit_unit))
        if len(self.writes) == self.fail_write_at:
            raise _OutcomeUnknownError


class _AsyncPackedClient:
    def __init__(self, *, fail_write_at: int | None = None, fail_read_at: int | None = None) -> None:
        self.fail_write_at = fail_write_at
        self.fail_read_at = fail_read_at
        self.read_count = 0
        self.writes: list[list[int]] = []

    async def __aenter__(self) -> _AsyncPackedClient:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def read_devices(self, _device: str, _points: int, *, bit_unit: bool) -> list[int]:
        assert bit_unit is False
        self.read_count += 1
        if self.read_count == self.fail_read_at:
            raise _ReadbackError
        return [0xA55A]

    async def write_devices(self, _device: str, values: list[int], *, bit_unit: bool) -> None:
        assert bit_unit is False
        self.writes.append(list(values))
        if len(self.writes) == self.fail_write_at:
            raise _OutcomeUnknownError


class _AsyncTypedClient:
    def __init__(self, *, fail_write_at: int | None = None, fail_read_at: int | None = None) -> None:
        self.fail_write_at = fail_write_at
        self.fail_read_at = fail_read_at
        self.read_count = 0
        self.writes: list[int] = []

    async def __aenter__(self) -> _AsyncTypedClient:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def read(self, _client: Any, _device: str, _dtype: str) -> int:
        self.read_count += 1
        if self.read_count == self.fail_read_at:
            raise _ReadbackError
        return 77

    async def write(self, _client: Any, _device: str, _dtype: str, value: int) -> None:
        self.writes.append(value)
        if len(self.writes) == self.fail_write_at:
            raise _OutcomeUnknownError


class _AsyncBitInWordClient:
    def __init__(self, *, fail_write_at: int | None = None, fail_read_at: int | None = None) -> None:
        self.fail_write_at = fail_write_at
        self.fail_read_at = fail_read_at
        self.read_count = 0
        self.writes: list[bool] = []

    async def __aenter__(self) -> _AsyncBitInWordClient:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def read(self, _client: Any, _addresses: list[str]) -> dict[str, bool]:
        self.read_count += 1
        if self.read_count == self.fail_read_at:
            raise _ReadbackError
        return {"D50.3": False}

    async def write(
        self,
        _client: Any,
        _device: str,
        *,
        bit_index: int,
        value: bool,
    ) -> None:
        assert bit_index == 3
        self.writes.append(value)
        if len(self.writes) == self.fail_write_at:
            raise _OutcomeUnknownError


def test_usage_python_blocks_compile() -> None:
    for document in (GETTING_STARTED, USAGE_GUIDE):
        blocks = _python_blocks(document.read_text(encoding="utf-8"))
        assert blocks
        for index, block in enumerate(blocks, 1):
            compile(
                block,
                f"{document.name}#python-{index}",
                "exec",
                flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT,
            )


def test_documentation_python_imports_resolve() -> None:
    for document in (GETTING_STARTED, USAGE_GUIDE):
        for index, block in enumerate(_python_blocks(document.read_text(encoding="utf-8")), 1):
            tree = ast.parse(block)
            imports = ast.Module(
                body=[node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))],
                type_ignores=[],
            )
            exec(compile(imports, f"{document.name}#imports-{index}", "exec"), {})


def test_state_changing_examples_preserve_confirmed_write_cleanup() -> None:
    markdown = USAGE_GUIDE.read_text(encoding="utf-8")
    blocks = _python_blocks(markdown)

    getting_started = _block_containing(
        _python_blocks(GETTING_STARTED.read_text(encoding="utf-8")),
        'write_typed(client, "D100", "U", 42)',
    )
    assert "write_confirmed = False" in getting_started
    assert "if write_confirmed:" in getting_started

    typed = _block_containing(blocks, 'write_typed(client, "D100", "U", 42)')
    assert "write_confirmed = False" in typed
    assert "if write_confirmed:" in typed

    bit_in_word = _block_containing(blocks, 'write_bit_in_word(client, "D50"')
    assert "write_confirmed = False" in bit_in_word
    assert "if write_confirmed:" in bit_in_word

    module = _block_containing(blocks, 'write_devices_extended("U3\\\\G100"')
    assert "write_confirmed = False" in module
    assert "finally:" in module
    assert 'write_devices_extended("U3\\\\G100", original' in module

    link = _block_containing(blocks, 'write_devices_extended("J1\\\\SW14"')
    assert "word_write_confirmed = False" in link
    assert "bit_write_confirmed = False" in link
    assert "from slmp import SlmpClient, SlmpOutcomeUnknownError, SlmpTarget" in link
    assert "except SlmpOutcomeUnknownError:" in link
    assert "if not outcome_unknown:" in link
    assert 'write_devices_extended("J1\\\\X11", original_bit' in link
    assert 'write_devices_extended("J1\\\\SW14", original_word' in link

    packed = _block_containing(blocks, 'write_devices("M1000"')
    assert 'read_devices("M1000", 1, bit_unit=False)' in packed
    assert "finally:" in packed
    assert 'write_devices("M1000", original' in packed

    warning = "Clear Error is a separate state-changing maintenance action."
    assert markdown.index(warning) < markdown.index("client.clear_error()")
    assert "If the write raises `SlmpOutcomeUnknownError`" in markdown
    assert "Always attempt re-lock after a confirmed unlock" in markdown
    assert "Monitor registration changes the PLC's active monitor set" in markdown


def test_module_example_restores_after_readback_failure_but_not_unknown_write() -> None:
    block = _block_containing(
        _python_blocks(USAGE_GUIDE.read_text(encoding="utf-8")),
        'write_devices_extended("U3\\\\G100"',
    )

    client = _SyncExtendedClient(fail_read_at=2)
    try:
        _run_sync_example(block, client)
    except _ReadbackError:
        pass
    else:
        raise AssertionError("the simulated readback failure must propagate")
    assert client.writes == [
        ("U3\\G100", [1, 2, 3, 4], False),
        ("U3\\G100", [10, 11, 12, 13], False),
    ]

    client = _SyncExtendedClient(fail_write_at=1)
    try:
        _run_sync_example(block, client)
    except _OutcomeUnknownError:
        pass
    else:
        raise AssertionError("the simulated outcome-unknown write must propagate")
    assert client.writes == [("U3\\G100", [1, 2, 3, 4], False)]


def test_link_example_restores_in_reverse_order_and_continues_cleanup() -> None:
    block = _block_containing(
        _python_blocks(USAGE_GUIDE.read_text(encoding="utf-8")),
        'write_devices_extended("J1\\\\SW14"',
    )

    client = _SyncExtendedClient()
    _run_sync_example(block, client)
    assert [device for device, _values, _bit_unit in client.writes] == [
        "J1\\SW14",
        "J1\\X11",
        "J1\\X11",
        "J1\\SW14",
    ]

    client = _SyncExtendedClient(fail_write_at=2)
    try:
        _run_sync_example(block, client)
    except _OutcomeUnknownError:
        pass
    else:
        raise AssertionError("the simulated bit outcome-unknown write must propagate")
    assert [device for device, _values, _bit_unit in client.writes] == [
        "J1\\SW14",
        "J1\\X11",
    ]

    client = _SyncExtendedClient(fail_write_at=3)
    try:
        _run_sync_example(block, client)
    except _OutcomeUnknownError:
        pass
    else:
        raise AssertionError("the simulated bit restoration failure must propagate")
    assert [device for device, _values, _bit_unit in client.writes] == [
        "J1\\SW14",
        "J1\\X11",
        "J1\\X11",
    ]


def test_packed_example_restores_after_readback_failure_but_not_unknown_write() -> None:
    block = _block_containing(_python_blocks(USAGE_GUIDE.read_text(encoding="utf-8")), 'write_devices("M1000"')

    client = _AsyncPackedClient(fail_read_at=2)
    try:
        asyncio.run(_run_async_example(block, client))
    except _ReadbackError:
        pass
    else:
        raise AssertionError("the simulated readback failure must propagate")
    assert client.writes == [[0x0005], [0xA55A]]

    client = _AsyncPackedClient(fail_write_at=1)
    try:
        asyncio.run(_run_async_example(block, client))
    except _OutcomeUnknownError:
        pass
    else:
        raise AssertionError("the simulated outcome-unknown write must propagate")
    assert client.writes == [[0x0005]]


def test_typed_examples_restore_after_readback_failure_but_not_unknown_write() -> None:
    for document in (GETTING_STARTED, USAGE_GUIDE):
        block = _block_containing(
            _python_blocks(document.read_text(encoding="utf-8")),
            'write_typed(client, "D100", "U", 42)',
        )

        client = _AsyncTypedClient(fail_read_at=2 if document == GETTING_STARTED else None)
        if document == GETTING_STARTED:
            try:
                asyncio.run(
                    _run_async_helper_example(
                        block,
                        client,
                        {"read_typed": client.read, "write_typed": client.write},
                    )
                )
            except _ReadbackError:
                pass
            else:
                raise AssertionError("the simulated readback failure must propagate")
        else:
            asyncio.run(
                _run_async_helper_example(
                    block,
                    client,
                    {"read_typed": client.read, "write_typed": client.write},
                )
            )
        assert client.writes == [42, 77]

        client = _AsyncTypedClient(fail_write_at=1)
        try:
            asyncio.run(
                _run_async_helper_example(
                    block,
                    client,
                    {"read_typed": client.read, "write_typed": client.write},
                )
            )
        except _OutcomeUnknownError:
            pass
        else:
            raise AssertionError("the simulated outcome-unknown write must propagate")
        assert client.writes == [42]


def test_bit_in_word_example_restores_after_readback_failure_but_not_unknown_write() -> None:
    block = _block_containing(
        _python_blocks(USAGE_GUIDE.read_text(encoding="utf-8")),
        'write_bit_in_word(client, "D50"',
    )

    client = _AsyncBitInWordClient(fail_read_at=2)
    try:
        asyncio.run(
            _run_async_helper_example(
                block,
                client,
                {"read_named": client.read, "write_bit_in_word": client.write},
            )
        )
    except _ReadbackError:
        pass
    else:
        raise AssertionError("the simulated readback failure must propagate")
    assert client.writes == [True, False]

    client = _AsyncBitInWordClient(fail_write_at=1)
    try:
        asyncio.run(
            _run_async_helper_example(
                block,
                client,
                {"read_named": client.read, "write_bit_in_word": client.write},
            )
        )
    except _OutcomeUnknownError:
        pass
    else:
        raise AssertionError("the simulated outcome-unknown write must propagate")
    assert client.writes == [True]
