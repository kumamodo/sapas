# 05 Connection Layer Guide (Protocols)

Sapas manages connections with the Device Under Test (DUT) uniformly through `ConnectionManager`.

## Driver Configuration (YAML)

You can define connection information in `station.yaml` or `project.yaml`:

```yaml
# Define connectivity for all physical hardware units
link:
  # --- MAIN DUT: Primary Device Under Test ---
  main_dut:
    type: ssh                # Connection type: supports ssh, adb, com
    host: 192.168.1.110      # Device IP address
    user: kumamodo           # Login username
    password: ''             # Login password
    stop_chars: ':~$'        # [Optional] Shell prompt termination characters
```

## Accessing Drivers (Python API)

Sapas provides two ways to retrieve connection instances in your scripts:

1.  **Universal Link Manager**: Use `sapas.link.get(name)` for any protocol.
2.  **Dedicated Context Managers**: Use `ctx.ssh.get(name)`, `ctx.adb.get(name)`, or `ctx.udp.get(name)` for better type hinting and protocol-specific validation.

---

## SSH Driver (SSHDriver)

Integrates command execution over SSH.

### Code Example:
```python
import sapas
from sapas.runtime.runtime import ctx

# Method A: Universal Access
ssh = sapas.link.get('main_dut')

# Method B: Dedicated Access
ssh = ctx.ssh.get('main_dut')

# Execute command
result = ssh.exec('uname -a')
print(result)
```

## ADB Driver (ADBDriver)

Supports Android devices with "Smart Dual-Mode" (USB priority with Network fallback) and "Auto-Discovery".

### Code Example:
```python
import sapas
from sapas.runtime.runtime import ctx

# Method A: Universal Access
device = sapas.link.get('adb_device')

# Method B: Dedicated Access
device = ctx.adb.get('adb_device')

# Execute shell command
model = device.exec('getprop ro.product.model')
print(model)
```

## UDP Driver (UDPDriver)

Used for communication with MCU or other network-based hardware via UDP packets.

### Configuration Example:
```yaml
link:
  mcu:
    type: udp
    host: "192.168.1.111"
    server_port: 5088
    client_port: 5088
```

### Code Example:
```python
from sapas.runtime.runtime import ctx

# Get UDP connection
udp = ctx.udp.get('mcu')

# Send command and get response
response = udp.exec('READ_VER')
print(response)
```

## Other Protocols (Planned)

- **UART (Serial)**: Used for serial port control.

All drivers are encapsulated under `sapas.drivers`, allowing developers to easily extend custom communication protocols.
