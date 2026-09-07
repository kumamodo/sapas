# 03 Configuration Guide (YAML Configuration)

Sapas adopts a multi-level YAML configuration system, allowing developers to flexibly manage global environments, project variables, and station settings.

## 1. Configuration Levels and Priority

When the system starts, it loads and deep-merges configuration files in the following order. **Later ones overwrite variables of the same name from earlier ones**:

1.  **`configs/project.yaml`** (Project Level Defaults - Lowest)
2.  **`stations/{STATION}/station.yaml`** (Station Level Standard Baseline - Tracked in Git)
3.  **`site_infra.yaml`** (Local Machine/Environment Level - Not in Git, Highest Override Priority)

**Priority Relationship**:
`site_infra.yaml` (Local Machine Override) > `stations/{STATION}/station.yaml` (Station Baseline) > `configs/project.yaml` (Project Defaults)

**Design Philosophy**:
*   **`station.yaml`** is tracked in Git and defines the **standard out-of-the-box hardware baseline** for each station (e.g., SMT standard PSU is GW Instek, FA standard PSU is ITECH).
*   **`site_infra.yaml`** is local to each physical machine (kept out of Git, e.g. via `.gitignore`), managing local factory infrastructure (MES/Shopfloor IP) as well as **machine-specific hardware overrides** (such as COM port differences or developer local testing setups).
*   **Zero Git Pollution for R&D**: When R&D engineers develop at their desks with different connections or ports, they can override `LINK` settings in their local `site_infra.yaml` without dirtying or breaking Git tracking for production lines.

---

## 2. Variable Access Interface: sapas.var

In the Sapas framework, all merged configurations and data dynamically generated during execution are treated as "global variables". Whether in a **Python Script** or a **Test Flow**, you can access or write them through `sapas.var`.

### Access and Write Methods:
*   **Read Variable**: Use `sapas.var.get("KEY_NAME")`.
*   **Write/Update Variable**: Use `sapas.var.set("KEY_NAME", value)`.

This makes `sapas.var` a powerful global data hub, facilitating the transfer of information between different test steps (e.g., storing a measurement in step A and making a judgment based on that value in step B).

---

## 3. The Purpose of Each Configuration File

### site_infra.yaml (Local Machine & Factory Infrastructure)
*   **Location**: Usually placed in the workspace root directory (e.g., `example/site_infra.yaml`, recommended to add to `.gitignore`).
*   **Purpose**: Machine-local environment configuration and local hardware overrides. Contains MES/Shopfloor IPs, site-wide parameters, and target `PROJECT_NAME` / `STATION_NAME` for the local PC.
*   **Typical Parameters**: `PROJECT_NAME`, `STATION_NAME`, `FACTORY_LOCATION`, `ENABLE_SHOPFLOOR`, `SMB_SERVER_IP`, `LINK` (local connection overrides).

### project.yaml (Project Definition)
*   **Location**: `{Project}/configs/project.yaml`.
*   **Purpose**: Defines logic and connection baselines used by all stations in the project. For example: shared DUT connections, expected firmware version, shared timeout periods.
*   **Typical Parameters**: `EXPECTED_FW_VER`, `TIMEOUT_RETRY`, `LINK`.

### station.yaml (Station Standard Baseline)
*   **Location**: `{Project}/stations/{StationName}/station.yaml`.
*   **Purpose**: Defines the standard factory equipment and test specifications for the station (tracked in Git).
*   **Typical Parameters**: `LINK` (station-specific equipment such as power supplies, fixture PLCs), `STATION_ID`.

---

## 4. System Core Reserved Variables

The following are key parameters referenced or automatically generated within the Sapas framework. Please avoid using them for unrelated purposes.

| Parameter Name | Type | Description |
| :--- | :--- | :--- |
| `PROJECT_NAME` | String | Project name. The system looks for the corresponding folder based on this. |
| `STATION_NAME` | String | Station name. The system looks for `station.yaml` and the default `.flow` based on this. |
| `TEST_FLOW` | String | Locks the test flow file to run for the current station (format: `FlowName.flow`). Only takes effect when defined in `site_infra.yaml`. |
| `IS_FAIL_STOP` | Boolean | If `True`, the test will immediately interrupt and jump to `on_fail` when a `verify` command fails. |
| `STATION_TIMEOUT` | Number | Total station execution time limit (in seconds). Default `0` means unlimited. If total execution time exceeds this threshold, the test aborts and marks `STATION_TIMEOUT` failure. |
| `IS_EXCEPTION_STOP` | Boolean | If `True`, the test will immediately interrupt when a script throws an exception or crashes (non-`80` return code). Set to `False` to debug alongside `IS_FAIL_STOP`. |
| `ENABLE_SHOPFLOOR`| Boolean | Indicates whether the current test is connected to Shopfloor. |
| `ENABLE_SMB` | Boolean | Whether to upload logs and data from the test process (usually `output/{Serial}`) to a server for later tracking. |
| `LINK` | Dict | Defines connection drivers (e.g. SSH, ADB, UDP, UART, POWER_SUPPLY). Contains sub-parameters such as `type`, `host`, `user`, `password`, `source_ip` (optional local PC NIC source IP), `drain_timeout` (optional UDP packet chunk drain timeout). The lowercase `link` key is deprecated. |
| `WORKSPACE_ROOT`| Path | (Auto-generated) Points to the root directory where the command is executed. |
| `ERROR_CODE` | String | (Generated at runtime) Current test status. Common values and meanings:<br>- `PASS`: Test passed successfully.<br>- `FAIL`: Test failed (usually due to a `verify` command failure).<br>- `CRITICAL`: Critical exception (script crash, syntax error, or connection lost).<br>- `STOP`: Test stopped manually by operator.<br>- `CHECK`: Does not mean the test failed. When you want to scan all test items quickly (e.g. setting `IS_FAIL_STOP=False`), the system sets the final status to `CHECK`, prompting the engineer to manually inspect the log or TUI to judge and verify the status of each test item. |
| `ERROR_DESCRIPTION`| String | (Generated at runtime) Detailed description when a failure occurs. |
| `RUNNER_LOGGER` | Object | (Internal) Logger object for Python scripts to call. |
