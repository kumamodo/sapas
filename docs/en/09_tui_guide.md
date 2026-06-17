# 09 TUI Dashboard Operation and Visual Manual

> **Target Audience**: Station Operators, Test Engineers, Equipment Integration Engineers  
> **Interface Version**: Sapas TUI Dashboard v0.1.0+

---

## 1. Interface Layout Overview

The Sapas TUI dashboard utilizes a three-tier vertical layout with a split-screen main body. It consolidates all critical test execution data into a single terminal screen, allowing operators to monitor the complete testing status without switching windows.

![Sapas TUI Dashboard Screenshot](../images/tui_screenshot.png)

### 1.1 Header

| Element | Description |
|------|------|
| **Sapas TUI Tester** | Application name |
| **)) Cycle N/N ((** | Current cycle / Total cycles (e.g., `Cycle 1/1`) |
| **HH:MM:SS** | System clock (24-hour format), displayed in the top-right corner |

---

### 1.2 Top Status Bar

The top status bar is divided into four independent panels:

#### 📌 Information Panel
Located on the left, displaying static environment info for the current station:

| Field | Description |
|------|------|
| `Station` | Name of the current test station |
| `Script` | Version number of the test script |
| `Flow` | The active test flow file (`.flow`) currently executing |

#### 📌 Error Code (Result Status)
Displays the overall decision/result of the current test run. Its background color changes in real time according to the status (see Section 2 for details).

#### 📌 Elapsed Time
Displays the accumulated time in seconds since the test was initiated (format: `HH:MM:SS.ss`), useful for estimating test progress.

#### 📌 Serial Number + Start
- **Serial Number Input Field**: The input box where operators type or scan the Unit Under Test (UUT) serial number. Highlighted with a yellow border when focused.
- **Start Button**: After inputting the serial number, press `Enter` or click this button to trigger the test sequence.

---

### 1.3 Main Body

The main body uses a split-screen layout:

#### Left: Items (Test Items List)

Lists all test steps configured for the current station in alternating zebra-striping rows:

| Field | Description |
|------|------|
| `Items` | Test step index and script name (e.g., `[01] get_os_name.py`) |
| `Status` | Current execution status of the step (PENDING / RUNNING / PASS / FAIL / SKIP) |

> During execution, the active `RUNNING` step will **automatically scroll** into view, eliminating the need for manual navigation.

#### Right: Live Log (Real-time Logs)

Displays raw outputs from the testing engine in a scrolling text area:

- `[ ITEM ]`: Boundary separator indicating the start of a test item
- `[ RUNNER ]`: Test framework runtime messages (e.g., snapshot export, resource cleanup)
- `[ ACTION ]`: Business logs triggered via `sapas.info()` in test scripts
- `[ USER ]`: Raw outputs from standard `print()` statements in user scripts
- `[ WARN ]`: Non-critical warning messages (displayed in yellow)
- `[ ERROR ]`: Critical error messages (displayed in red)

Once the test run completes, a **Result Banner** overlays the center area (see Section 2 for details).

---

### 1.4 Footer

| Section | Description |
|------|------|
| **Keyboard Shortcuts** | Lists currently available keyboard hotkeys (e.g., `^q Quit`, `f2 Serial Number`) |
| **Connection Status** | Displays the real-time Shopfloor connection status: **SHOPFLOOR ONLINE** or **SHOPFLOOR OFFLINE** |

> ⚠️ **Warning**: If Shopfloor is offline, the footer text turns red and the **entire dashboard border turns red**, alerting operators that test results cannot be uploaded to the factory server.

---

## 2. Status Indicators and Visual Semantics

### 2.1 Test Step Status (Items Column)

| Status | Color | Meaning | Operator Action Guide |
|----------|------|------|-------------|
| `PENDING` | Off-white | Waiting in queue, not started yet | Normal wait state, no action required |
| `RUNNING` | Yellow (blinking) | Step is actively executing | Do not move the unit; do not force quit |
| `✓ PASS` | Bright green | Test step passed successfully | Normal status, continue waiting |
| `✗ FAIL` | Red | Test step failed | Once testing stops, troubleshoot based on the failed item |
| `- SKIP` | Blue-gray | Step skipped (non-error) | Normal; usually skipped due to conditional logic or pre-requisite failures |

---

### 2.2 Error Code (Overall Decision)

| Display | Color | Meaning | Operator Action Guide |
|----------|------|------|-------------|
| `PASS` | 🟢 Bright Green | All test steps passed | Attach PASS label; dispatch unit to the next station |
| `CHECK` | 🟡 Yellow | Manual verification required | Call the test engineer to verify; **DO NOT release the unit** |
| `FAIL` | 🔴 Red | Test failed (at least one step failed) | Quarantine the unit; submit a defect report based on the failed items |

---

### 2.3 Live Log Color Semantics

| Log Prefix | Color | Meaning |
|------|------|------|
| `[ ACTION ]` | White | General script output / execution logs |
| `[ WARN ]` | 🟡 Yellow | Non-critical warning; test execution continues |
| `[ ERROR ]` | 🔴 Red | Critical error; may cause subsequent steps to fail |
| `[ RUNNER ]` | Gray-blue | Test engine framework messages (snapshots, system teardown) |
| `[ ITEM ]` | Blue-white | Test step boundary line |
| `[ USER ]` | Default foreground | Raw text from `print()` statements in scripts |
| `[ DELAY ]` | Cyan | Countdown info from delay timers |

---

### 2.4 Result Banner (Post-Test Overlay)

Upon completion, a large banner overlays the center section of the Live Log, providing immediate visual confirmation via text and border color:

![PASS Result Banner](../images/tui_pass_banner.png)

| Banner Style | Border Color | Text Color | Meaning |
|-------------|----------|----------|---------|
| `PASS ... UNIT ACCEPTED` | 🟢 Green | 🟢 Green | All tests passed; unit is accepted |
| `CHECK ... MANUAL CHECK REQUIRED` | 🟡 Yellow | 🟡 Yellow | Pending review; manual check required |
| `FAIL ... TEST FAILED` | 🔴 Red | 🔴 Red | Test failed; unit is rejected |

---

## 3. Operation Guide

### 3.1 Launching the TUI Dashboard

```bash
# Run in the working directory (e.g., example/)
sapas --tui
```

Or target a specific project and station:

```bash
sapas --tui --project Alishan --station Function
```

---

### 3.2 Standard Testing SOP Flow

```
① Confirm "SHOPFLOOR ONLINE" in footer (if shopfloor reporting is required)
         │
         ▼
② Scan or enter unit serial number into the Serial Number input field
         │
         ▼
③ Press Enter or click [ Start ] to start the test
         │
         ▼
④ Monitor the left Items panel: the RUNNING item will automatically scroll into view
         │
         ▼
⑤ Wait for all items to complete execution, and the result Banner appears in the center
         │
         ▼
⑥ Take subsequent actions based on the Banner color and text (Release / Repair / Call Engineer)
         │
         ▼
⑦ Scan the next unit serial number to enter the next test cycle
```

---

### 3.3 Keyboard Shortcuts Overview

| Shortcut | Function |
|--------|------|
| `Ctrl+Q` / `Ctrl+C` | Request to exit TUI (pops up confirmation dialog, defaults to "No" to prevent accidental exits) |
| `F2` | Focuses cursor back to the Serial Number input field |
| `F3` | Cycle through UI color themes (Theme Cycle) |
| `F4` | Toggle System Device Manager overlay |
| `F6` | Toggle Network Adapter Manager overlay |
| `Y` / `N` / `Escape` | Quick responses in the quit confirmation dialog |

---

### 3.4 Exiting the Dashboard

Pressing `Ctrl+Q` or `Ctrl+C` triggers a confirmation overlay in the center:

![Quit Confirmation Dialog](../images/tui_quit_dialog.png)

- **Default focus is on "No"** (indicated by a white border) to prevent operators from accidentally exiting mid-test by hitting `Enter`.
- Press `Y` to confirm exit, or `N` / `Escape` to return to the active dashboard without touching the mouse.

> ⚠️ **Warning**: Exiting while a test is running will **stop execution after the current step completes**. The test results will not be fully uploaded to the Shopfloor.

---

### 3.5 Device Manager

Press `F4` to open the System Device Manager overlay, which scans and lists all connected system hardware:

![System Device Manager](../images/tui_device_manager.png)

| Column | Description |
|------|------|
| `Device Name` | Name of the hardware device (e.g., USB Controller, COM Port) |
| `Port` | Associated communications port number (displays `—` if not applicable) |
| `Status` | Device status (`OK` in green / error state in red) |

- **Refresh (F5)**: Re-scans all hardware devices, useful after plugging in new devices.
- **Close (Esc)**: Closes the overlay and returns to the main dashboard.

---

### 3.6 Network Adapter Manager

Press `F6` to open the Network Adapter Manager overlay, displaying the status of all network interfaces:

![Network Adapter Manager](../images/tui_network_manager.png)

| Column | Description |
|------|------|
| `Adapter Name` | Network adapter name (e.g., Wi-Fi, Ethernet) |
| `IP Address` | The currently assigned IP address |
| `Link Speed` | Speed of the active network link (e.g., `866.7 Mbps`) |
| `Status` | Connection status (`Up` in white / `Disconnected` in orange) |

- **Refresh (F5)**: Re-scans all network interfaces.
- **Close (Esc)**: Closes the overlay and returns to the main dashboard.

> 💡 **Tip**: If the Shopfloor indicator shows offline, open this manager to verify whether a valid IP address has been assigned.

---

## 4. Shopfloor Connection Status

| Border Color | Footer Message | Meaning | Important Note |
|----------|----------|------|----------|
| 🟢 Green Border | `SHOPFLOOR ONLINE` | Connected to Shopfloor system | Test results will upload automatically |
| 🔴 Red Border (Blinking) | `SHOPFLOOR OFFLINE` | Failed to connect to Shopfloor | Results **will not** upload; notify IT/Test Engineer immediately |

---

## 5. Common Issues and Troubleshooting

| Symptom | Potential Cause | Recommended Action |
|------|----------|-------------|
| Outer border flashes red | Shopfloor system is offline | Contact IT to check network health or Shopfloor services |
| A specific step shows `SKIP` | Pre-requisite step failed or conditions not met | Check the preceding failed step and address the root cause |
| `Error Code` displays `CHECK` | Certain test items require manual visual validation | Contact the test engineer; do not dispatch the unit to next station |
| Start button is unresponsive | Serial number field is empty, or a test is already running | Check if the serial number is entered, or wait for active run to end |
| Live Log output overflows the pane | Voluminous logs generated | Use scrollbars to review history; automatically clears on next test |
