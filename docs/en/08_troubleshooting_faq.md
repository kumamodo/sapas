# 08 Troubleshooting & FAQ (Troubleshooting)

This document lists common errors you may encounter when using the Sapas framework, their causes, and solutions.

---

## 1. Startup and Configuration Issues

### Q: `[Error] Project or Station not specified!` appears
- **Cause**: When executing `sapas`, the `--project` or `--station` parameters were not provided, and no default values are defined in `site_infra.yaml`.
- **Solution**:
  1. Add parameters to the command: `sapas --project Alishan --station Function`.
  2. Or add `PROJECT_NAME` and `STATION_NAME` in `site_infra.yaml`.

### Q: `Station config not found: .../station.yaml` appears
- **Cause**: The system cannot find the corresponding station configuration file under the specified project path.
- **Solution**: Check the directory structure to ensure the path is `{Project}/stations/{Station}/station.yaml`. Note that the case must match exactly.

### Q: `Required variable '...' not found.` appears
- **Cause**: The script called `sapas.var.require()`, but the variable is not defined in any YAML file.
- **Solution**: Check if the variable is missing from `site_infra.yaml`, `project.yaml`, or `station.yaml`.

---

## 2. Flow and Script Execution Issues

### Q: `Script not found: my_script.py` appears
- **Cause**: The script name specified in the `.flow` file cannot be found in the project's `scripts/` directory.
- **Solution**: Ensure the script has a `.py` extension and is placed in the correct `scripts/` folder.

### Q: Test result shows `Exception`
- **Cause**: The Python script crashed (Runtime Error) during execution, preventing measurements from being uploaded normally.
- **Solution**: Check the Traceback information in the logs to locate the line where the error occurred. Common causes include improper handling of null values or division by zero.

### Q: Why did the `if` condition fail?
- **Cause**: Sapas's `if` currently only supports `==` syntax, and both sides are converted to strings for comparison.
- **Solution**: Ensure that variable values in YAML exactly match the comparison values in the `.flow`. For example, if `ENABLE == True` is used in the flow but `ENABLE: true` (lowercase) is written in YAML, the comparison may fail.

---

## 3. Connection and Driver Issues

### Q: SSH connection failed: `Failed to connect to ...`
- **Cause**: Network issues, incorrect IP, wrong username/password, or the target machine does not have the SSH service enabled.
- **Solution**:
  1. Use manual tools (such as PuTTY or the `ssh` command) to confirm connectivity.
  2. Check the `link` configuration in `project.yaml` or `station.yaml`.

### Q: SFTP upload/download error
- **Cause**: Insufficient permissions (Permission Denied) or the remote directory does not exist.
- **Solution**: Ensure the remote path has write permissions, or use `ssh.exec("mkdir -p ...")` to create the directory first.

---

## 4. Judgment and Result Issues

### Q: `Test item does not exist in the CSV.` appears
- **Cause**: You used `self.measure.ITEM_A = 10` in the script, but `ITEM_A` is missing from the corresponding `criteria_file` (CSV).
- **Solution**: Add the corresponding test item name to the CSV file, ensuring spelling and case match exactly.

### Q: Why are all test item results `NA`?
- **Cause**: The script executed successfully, but `self.measure` was never called to assign values.
- **Solution**: Check script logic to ensure that measurements are uploaded for every test path.

---

## 5. Other Environmental Issues

### Q: Windows terminal logs show garbled characters
- **Cause**: The default encoding of the Windows terminal is not UTF-8.
- **Solution**: Sapas has built-in encoding handling, but it is recommended to switch the terminal (e.g., CMD or PowerShell) to UTF-8 mode, or use the terminal built into VS Code.

### Q: How to adjust the timeout?
- **Solution**: You can pass the `timeout` parameter when calling `ssh.exec(command, timeout=5)`. For global adjustments, it is recommended to define a variable in `project.yaml` for all scripts to reference.
