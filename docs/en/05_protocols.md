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

## SSH Driver (SSHDriver)

Currently, Sapas primarily supports SSH connections, integrating command execution.

### Code Example:
```python
from sapas.runtime.runtime import ctx

# Get SSH connection
ssh = ctx.ssh.get('main_dut')

# Execute command
result = ssh.exec('uname -a')
print(result.stdout)
```

## Other Protocols (Planned)

- **ADB**: Used for communication with Android devices.
- **UART (Serial)**: Used for serial port control.

All drivers are encapsulated under `sapas.drivers`, allowing developers to easily extend custom communication protocols.
