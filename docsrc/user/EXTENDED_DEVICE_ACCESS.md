# Extended device access

Use the extended-device APIs for routed device forms such as `Un\G...`,
`Un\HG...`, and `Jn\...`.

Normal typed and named helpers cover public device families such as `D`, `M`,
`X`, and `Y`. `G` and `HG` are not standalone normal-device routes.

## Module buffer access

Access intelligent module buffer memory with `read_devices_ext()` and
`write_devices_ext()`.

| Notation | Description | Example |
| --- | --- | --- |
| `Un\G` | Buffer memory word access | `U3\G100` |
| `Un\HG` | Extended buffer memory word access | `U3E0\HG1000` |

```python
from slmp import ExtensionSpec, SlmpClient


def main() -> None:
    with SlmpClient("192.168.250.100", port=1025, plc_profile="melsec:iq-r") as client:
        values = client.read_devices_ext("U3\\G100", 4, extension=ExtensionSpec())
        client.write_devices_ext("U3\\G100", [1, 2, 3, 4], extension=ExtensionSpec())
        print(values)


main()
```

`Un` is the module number in hexadecimal text, for example `U3` or `U3E0`.
Direct `G` / `HG` access without the `Un\` prefix is not supported.

## Link direct device access

Use link direct device notation for devices on a CC-Link IE network routed
through the connected PLC.

| Access type | Example |
| --- | --- |
| Word read/write | `J2\SW10`, `J1\W13` |
| Bit read/write | `J1\X10`, `J1\SB10` |

```python
from slmp import ExtensionSpec, SlmpClient


def main() -> None:
    with SlmpClient("192.168.250.100", port=1025, plc_profile="melsec:iq-r") as client:
        value = client.read_devices_ext("J2\\SW10", 1, extension=ExtensionSpec())
        bits = client.read_devices_ext("J1\\X10", 16, extension=ExtensionSpec(), bit_unit=True)
        client.write_devices_ext("J1\\SW14", [2], extension=ExtensionSpec())
        client.write_devices_ext("J1\\X11", [True], extension=ExtensionSpec(), bit_unit=True)
        print(value, bits)


main()
```

The available link direct device families depend on the PLC route and link
module configuration.

## Target station routing is separate

`SlmpTarget` controls the SLMP destination header. It does not replace routed
device notation such as `Un\G...` or `Jn\...`.

For target station, multi-CPU, and other-station routing, see the
[Usage guide](USAGE_GUIDE.md).
