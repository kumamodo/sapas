# 06 Script Development Reference (API Reference)

This document details the APIs, class attributes, and decorators available when writing Sapas test scripts (Python).

---

## 1. Core Classes: TestItem vs. ActionItem

In Sapas, scripts are divided into two main categories based on their purpose:

| Category | Purpose | Judgment Rule | Required Attributes |
| :--- | :--- | :--- | :--- |
| **`TestItem`** | Core test item (e.g., voltage measurement) | Must compare with CSV specifications to produce PASS/FAIL | Yes (5 attributes) |
| **`ActionItem`**| Utility script (e.g., initialization, report upload) | Only checks if the script crashes; no CSV comparison needed | No (no attributes required) |

---

## 2. TestItem Development Specifications

`TestItem` is the most core development class in Sapas. When you use the `verify` command in a Flow, the system expects to execute a `TestItem`.

### Interaction with Flow
When a Flow executes `verify my_test.py`:
1. **Instantiation**: The system loads `TestItem` and initializes the environment.
2. **Execution**: Calls the `run_test()` method.
3. **Judgment**: After the script finishes, `ResultManager` compares the data in `sapas.measure` with the `criteria_file`.
4. **Flow Control**: If the judgment result is **FAIL**, the Flow immediately interrupts and jumps to the `on_fail` block.

### Required Attributes
To allow the system to process data automatically, a `TestItem` must define the following five file path attributes:
- **`measure_file`**: Filename of the plain text file for temporary measurement storage.
- **`result_file`**: Filename of the CSV file for final judgment results.
- **`criteria_file`**: Filename of the CSV file for comparison specifications (must be located in the project's `criteria/` directory).
- **`logs_folder`**: Name of the log folder dedicated to this test item.
- **`logs_name`**: Filename of the log file for this test item.

### Required Methods
- **`run_test(self)`**: The main entry point for test logic. In this method, you must return key data via `sapas.measure`.

### TestItem Standard Template
```python
import sapas

class MyOsTest(sapas.TestItem):
    # 5 required path attributes
    measure_file  = "os_check.txt"
    result_file   = "os_check_result.csv"
    criteria_file = "os_check_criteria.csv"
    logs_folder   = "OS_CHECK_LOGS"
    logs_name     = "os_check.log"

    def run_test(self):
        sapas.info("Starting OS version check...")
        
        # 1. Execute action (e.g., get data via SSH or local command)
        # Example: get system information
        raw_output = "Microsoft Windows [Version 10.0.19045.4291]" 
        
        # 2. Process data
        extracted_name = "Windows" if "Windows" in raw_output else "Other"
        
        # 3. Record measurement (the name "OS_NAME" must exist in the criteria_file)
        sapas.measure.OS_NAME = extracted_name
        
        sapas.info(f"Extracted OS name: {extracted_name}")
```
---

## 3. ActionItem Development Specifications

`ActionItem` is suitable for cases where you only need to execute an action without recording measurements.

### Required Methods
- **`run_action(self)`**: The main entry point for action execution.

### ActionItem Standard Template
```python
import sapas

class SetupSystem(sapas.ActionItem):
    def run_action(self):
        sapas.info("Performing system initialization...")
        ssh = sapas.link.get("main_dut")
        ssh.exec("rm -rf /tmp/old_logs")
        sapas.info("Cleanup complete")
```

### Development Notes
1. **Log Tag**: The default tag for `ActionItem` logs is `[  USER  ]`.
2. **No Judgment Result**: It does not produce a `result.csv`. If an exception is thrown during script execution, the flow is considered failed.
3. **Recommended Uses**: Suitable for environment setup (Setup), result reporting (Reporting), or rollback handling (on_fail) in `flows`.

---

## 4. Data Measurement and Judgment (sapas.measure)

`sapas.measure` is a proxy object that allows you to directly map measured values to items in `criteria`.

```python
def run_test(self):
    # Assume there is a test item called "CPU_TEMP" in the criteria CSV
    temp = 45.5
    sapas.measure.CPU_TEMP = temp  # Automatically records the measurement
    
    # Assume there is a string comparison test item called "OS_NAME"
    sapas.measure.OS_NAME = "Windows"
```

> **Note**: If the attribute name you assign does not exist in the `criteria_file`, the system will throw an error immediately.

---

## 5. Variable Access (sapas.var)

`sapas.var` is used to access variables defined in `YAML` configuration files or to pass dynamic data between different scripts.

- **`sapas.var.get(key, default=None)`**: Gets the variable value.
- **`sapas.var.set(key, value)`**: Sets or updates the variable value (limited to the current test cycle).
- **`sapas.var.require(key)`**: Gets the variable; throws an exception if it doesn't exist.

```python
import sapas

def run_test(self):
    # Get setting from YAML
    timeout = sapas.var.get("TIMEOUT_RETRY", 10)
    
    # Record measured MAC to Context for use by subsequent scripts
    sapas.var.set("DUT_MAC", "AA:BB:CC:DD:EE:FF")
```

---

## 6. Connection Driver (sapas.link)

`sapas.link` is used to get connection objects defined in `station.yaml`.

```python
import sapas

def run_test(self):
    # Get SSH connection named 'main_dut'
    ssh = sapas.link.get("main_dut")
    
    # Execute command and get results
    result = ssh.exec("uname -a")
    sapas.info(f"OS Version: {result.stdout}")
```

---

## 7. Log Output

Within a script, it is recommended to use the global log functions provided by `sapas`. The system automatically detects the current script execution context (`TestItem` or `ActionItem`), applies the correct tag, and outputs the logs simultaneously to the console and the corresponding log file.

- **`sapas.info(msg)`**: Records general information. Displayed as `[  USER  ]` in `TestItem` and `[ ACTION ]` in `ActionItem`.
- **`sapas.warn(msg)`**: Records warning information (Tag: `[  WARN  ]`).
- **`sapas.error(msg)`**: Records error information (Tag: `[ ERROR  ]`).

```python
import sapas

class LogDemo(sapas.ActionItem):
    def run_action(self):
        sapas.info("This is a general info log")
        sapas.warn("This is a warning log")
        sapas.error("This is an error log")
```

---

## 8. Built-in Delay (sapas.sleep)

To prevent timeline opacity caused by standard Python `time.sleep()`, Sapas provides a built-in delay helper:

- **`sapas.sleep(seconds)`**: Delays execution for the specified duration (supports float and integer seconds) and logs a real-time countdown.

```python
import sapas

class SleepDemo(sapas.ActionItem):
    def run_action(self):
        sapas.info("Preparing to send Shopfloor data...")
        # Delay for 5.5 seconds with live countdown logs
        sapas.sleep(5.5)
        sapas.info("Data sent successfully")
```

Running this script outputs the following logs dynamically:
```text
[ ACTION ] [DELAY] Sleep for 5.5 seconds.
[ ACTION ] [DELAY] Countdown 6 sec...
[ ACTION ] [DELAY] Countdown 5 sec...
[ ACTION ] [DELAY] Countdown 4 sec...
[ ACTION ] [DELAY] Countdown 3 sec...
[ ACTION ] [DELAY] Countdown 2 sec...
[ ACTION ] [DELAY] Countdown 1 sec...
[ ACTION ] [DELAY] Countdown 0.5 sec...
[ ACTION ] [DELAY] Sleep finished.
```

---

## 9. Custom Arguments (@sapas.arg)

If you need to pass arguments from a `.flow` to a script, you can use the `@sapas.arg` decorator.

```python
@sapas.arg("--mode", type=str, default="normal", help="Test mode")
class MyTest(sapas.TestItem):
    ...
    def run_test(self):
        # Access arguments via self.args
        current_mode = self.args.mode
        sapas.info(f"Current mode is: {current_mode}")
```

Calling method in `.flow`:
```yaml
verify my_custom_test.py --mode fast
```

---

## 10. Standard Script Template

```python
import sapas
import sys

@sapas.arg("--threshold", type=float, default=50.0)
class StandardTest(sapas.TestItem):
    measure_file  = "std_measure.txt"
    result_file   = "std_result.csv"
    criteria_file = "std_criteria.csv"
    logs_folder   = "STD_LOGS"
    logs_name     = "std.log"

    def run_test(self):
        sapas.info("Starting standard test...")
        
        # 1. Get connection and arguments
        ssh = sapas.link.get("main_dut")
        limit = self.args.threshold
        
        # 2. Execute action
        output = ssh.exec("cat /proc/uptime").stdout
        uptime = float(output.split()[0])
        
        # 3. Record measurements (corresponding to criteria CSV)
        sapas.measure.UPTIME = uptime
        sapas.measure.STATUS = "1" if uptime > limit else "0"
        
        sapas.info(f"Test complete, Uptime: {uptime}")
```
---

## 11. Script Debugging Method

To ensure scripts run correctly within the Sapas environment, it is **not recommended** to execute them directly using `python script.py`. Please use the CLI command provided by Sapas for debugging:

```bash
# Debug a single script
sapas <script_name>
```

This ensures the system automatically loads the corresponding YAML configurations and connection information, simulating the most realistic execution environment.
