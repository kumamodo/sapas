# 04 Data Specifications (Criteria Format)

To achieve automated judgment, Sapas uses CSV-formatted Criteria to define specifications. Please refer to `example/Alishan/criteria/`.

## Criteria CSV Format Example

Taking `get_os_name_criteria.csv` used by the `Function` station as an example:

| Test Item | LSL | USL | Measured | Status | Description | ErrCode |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| OS_NAME | Windows | Windows | | | Check if the OS is Windows | E101 |
| CPU_SERIAL | RECORD | RECORD | | | Record CPU serial number | |

### Judgment Rules:
- **Numerical Comparison**: If `LSL` and `USL` are numbers, the system checks if the measured value is within range.
- **String Comparison**: If `LSL == USL` and they are strings, an exact match is performed.
- **RECORD**: Regardless of the measured value, the result is PASS; used only for data recording.
- **ErrCode**: Error code generated upon failure. Supports `CodeLow:CodeHigh` format.

## Measurement & Validation Flow

Sapas tightly integrates script development with automated judgment. Below is the complete flow from development to result output:

1.  **Script Development Principles**:
    *   **Uppercase Naming**: Test Item names in code and CSV must always use uppercase snake_case (e.g., `OS_NAME`).
    *   **Data Return**: During script execution, pass data to `ResultManager` via the `sapas` API.

2.  **Automated Processing Steps**:
    *   **Start**: `Runner` initiates commands in the `.flow` file.
    *   **Execute**: The script (e.g., `get_os_name.py`) runs and produces a measured value (e.g., `Windows`).
    *   **Load**: `ResultManager` automatically reads the corresponding Criteria CSV (e.g., `get_os_name_criteria.csv`).
    *   **Compare**: The system compares the measured value with the `LSL/USL` in the CSV.
    *   **Report**: Judges the result (PASS/FAIL), records the status, and generates the final test report.

## Duplicate Test Items & Parameterization

When the same test script needs to be executed multiple times in a Flow file (e.g., measuring voltage before and after power-on), Sapas supports **parameterized fields** and **tag mapping** to prevent subsequent test results from overwriting previous ones:

### 1. Define Criteria Placeholder with `{}`
In the Criteria CSV, add the `{}` placeholder to the name of the duplicate test item, e.g., `VOLTAGE_{}`:

| Test Item | LSL | USL | Measured | Status | Description | ErrCode |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| VOLTAGE_{} | 4.5 | 13.0 | | | Verify system voltage | E0001 |

### 2. Differentiate in Flow using `--sapas-tag`
In the `.flow` file, specify a suffix tag for different stages of the test via `--sapas-tag <Value>`:
```text
verify verify_voltage.py --sapas-tag FIRST
prompt --text "Please adjust voltage to 12V..."
verify verify_voltage.py --sapas-tag SECOND
```

### 3. Transparent Code Mapping (Decoupled Logic)
Custom Python scripts do not need to perform any string formatting; simply write to the standard variable name:
```python
sapas.measure.VOLTAGE = 5.05
```
The Sapas framework automatically maps `VOLTAGE` to `VOLTAGE_FIRST` or `VOLTAGE_SECOND` behind the scenes.

### 4. Strict Validation (Poka-yoke)
To prevent human configuration mistakes, Sapas enforces strict bi-directional validation:
- If the Criteria CSV contains `{}`, the Flow file **must** include the `--sapas-tag` argument.
- If the Criteria CSV does not contain `{}`, the Flow file **must not** include the `--sapas-tag` argument.
If there is a mismatch, the test engine raises a `ValueError` at startup and aborts execution.
