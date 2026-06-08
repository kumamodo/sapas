# 03 Configuration Guide (YAML Configuration)

Sapas adopts a multi-level YAML configuration system, allowing developers to flexibly manage global environments, project variables, and station settings.

## 1. Configuration Levels and Priority

When the system starts, it loads and merges configuration files in the following order. **Later ones will overwrite variables of the same name from earlier ones**, meaning that the most specific "Station Configuration" has the highest priority:

1.  **`site_infra.yaml`** (Global/Environment Level)
2.  **`configs/project.yaml`** (Project Level)
3.  **`stations/{STATION}/station.yaml`** (Station Level)

**Priority Example**:
`stations/Function/station.yaml` > `configs/project.yaml` > `site_infra.yaml`

**Application Scenario**:
Suppose `FACTORY_LOCATION: Chiayi` is defined in `site_infra.yaml`.
*   In `function.flow`, you can directly use this variable for logic judgment.
*   In a Python script, you can also access it through the API.

---

## 2. Variable Access Interface: sapas.var

In the Sapas framework, all merged configurations and data dynamically generated during execution are treated as "global variables". Whether in a **Python Script** or a **Test Flow**, you can access or write them through `sapas.var`.

### Access and Write Methods:
*   **Read Variable**: Use `sapas.var.get("KEY_NAME")`.
*   **Write/Update Variable**: Use `sapas.var.set("KEY_NAME", value)`.

This makes `sapas.var` a powerful global data hub, facilitating the transfer of information between different test steps (e.g., storing a measurement in step A and making a judgment based on that value in step B).

---

## 3. The Purpose of Each Configuration File

### site_infra.yaml (Environment Infrastructure)
*   **Location**: Usually placed in the workspace root directory (e.g., `example/`).
*   **Purpose**: Information shared across projects. For example, all stations in the same factory connect to the same Shopfloor system.
*   **Typical Parameters**: `FACTORY_LOCATION`, `ENABLE_SHOPFLOOR`, `SMB_SERVER_IP`.

### project.yaml (Project Definition)
*   **Location**: `{Project}/configs/project.yaml`.
*   **Purpose**: Defines logic used by all stations in the project. For example: expected firmware version, shared timeout periods.
*   **Typical Parameters**: `EXPECTED_FW_VER`, `TIMEOUT_RETRY`.

### station.yaml (Station Hardware)
*   **Location**: `{Project}/stations/{StationName}/station.yaml`.
*   **Purpose**: Defines information unique to "this specific machine". Even for the same project, IPs or COM Ports of different stations are usually different.
*   **Typical Parameters**: `link` (Connection driver configuration), `STATION_ID`.

---

## 4. System Core Reserved Variables

The following are key parameters referenced or automatically generated within the Sapas framework. Please avoid using them for unrelated purposes.

| Parameter Name | Type | Description |
| :--- | :--- | :--- |
| `PROJECT_NAME` | String | Project name. The system looks for the corresponding folder based on this. |
| `STATION_NAME` | String | Station name. The system looks for `station.yaml` and the default `.flow` based on this. |
| `IS_FAIL_STOP` | Boolean | If `True`, the test will immediately interrupt and jump to `on_fail` when a `verify` command fails. |
| `ENABLE_SHOPFLOOR`| Boolean | Indicates whether the current test is connected to Shopfloor. |
| `ENABLE_SMB` | Boolean | Whether to upload logs and data from the test process (usually `output/{Serial}`) to a server for later tracking. |
| `link` | Dict | Defines connection drivers (e.g., SSH). Contains sub-parameters like `driver`, `host`, `user`, etc. |
| `WORKSPACE_ROOT`| Path | (Auto-generated) Points to the root directory where the command is executed. |
| `ERROR_CODE` | String | (Generated at runtime) Current test status. Common values: `PASS`, `FAIL`, `CRITICAL`, `STOP`. |
| `ERROR_DESCRIPTION`| String | (Generated at runtime) Detailed description when a failure occurs. |
| `RUNNER_LOGGER` | Object | (Internal) Logger object for Python scripts to call. |
