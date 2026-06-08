# 07 Quick Station Setup Guide (Station Setup)

This guide will walk you through building a brand new test station from scratch within an existing project (using `Alishan` as an example).

## Four Steps to Create a Station

Assuming we want to create a new station named `Final_Check`, please follow these steps:

### Step 1: Create Station Folder and Configuration
Create a folder with the same name as the station under the `stations/` directory and add a `station.yaml` file.
- **Path**: `example/Alishan/stations/Final_Check/station.yaml`
- **Content**: Define connection information specific to that machine.
  ```yaml
  # station.yaml Example
  STATION_LOCATION: FA
  FIXTURE_ID: 002

  PSU_COM_PORT: COM9
  PSU_BAUDRATE: 9600

  FIXTURE_PLC_TYPE: SOCKET
  FIXTURE_PLC_SOCKET_PORT: 5001
  FIXTURE_CTL_SOCKET_PORT: 5002
  TUI_SOCKET_PORT: 2003

  NOISE_SENSOR_COM_PORT: COM25
  NOISE_SENSOR_BAUDRATE: 9600
  ```

### Step 2: Define Test Flow (Flow)
Create a `.flow` file in the `flows/` directory. It is recommended that the filename match the station name.
- **Path**: `example/Alishan/flows/final_check.flow`
- **Content**: Use `verify` or `action` to chain your test scripts.
  ```yaml
  start final_check
      cycle 1
          action demo_logs.py
          verify get_os_name.py
          # You can add more custom scripts here
  stop
  
  on_fail
      action sleep.py --sec 2
  end
  ```

### Step 3: Prepare Test Scripts (Scripts)
Place your Python test logic in the `scripts/` directory.
- **Path**: `example/Alishan/scripts/my_custom_test.py`
- **Key Points**:
  - Use `sapas.var.get()` to read configurations.
  - Use `self.measure` to record test results (refer to API documentation for details).

### Step 4: Set Judgment Specifications (Criteria)
Create a CSV specification file corresponding to the script in the `criteria/` directory.
- **Path**: `example/Alishan/criteria/my_custom_test_criteria.csv`
- **Content**: Define test item names, upper and lower limits (LSL/USL), and error codes.

---

## How to Execute the New Station?

After completing the above steps, switch to the working directory and execute:

```bash
cd example
sapas --project Alishan --station Final_Check
```

The system will automatically find:
1. `stations/Final_Check/station.yaml` to load configurations.
2. `flows/final_check.flow` to execute the flow.

---

## Common Questions Q&A

**Q: Can my test scripts be placed outside the project folder?**
---
A: It is recommended to place them in the `scripts/` directory within the project for easier management.

**Q: Why was my new script executed, but I don't see any judgment results?**
---
A: Please check:
1. If there is a corresponding CSV file under `criteria/`.
2. If the test item names in the CSV match those uploaded in the script (note the case).
