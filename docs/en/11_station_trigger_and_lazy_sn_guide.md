# 11 Station Trigger & Lazy SN Guide

`Sapas Station Trigger & Lazy SN` is an automated orchestration, external IPC trigger, and industrial safety interlock subsystem designed specifically for **Automated Production Lines**, **Robotic Arms**, **Pneumatic Dark-box Fixtures**, and **Smart Factories**.

It bridges the architectural gap between **automated robotic execution** and **manual operator barcode scanning**, while integrating with **Station Guard** to enforce rigorous **Industrial Safety Interlocks**, eliminating the catastrophic risk of remote engineers actuating fixtures while on-site operators have their hands inside.

---

## 📑 Table of Contents
- [1. Motivation & Core Challenges](#1-motivation--core-challenges)
- [2. System Architecture & Communication Model](#2-system-architecture--communication-model)
- [3. CLI Command Reference](#3-cli-command-reference)
- [4. Lazy Serial Number Binding](#4-lazy-serial-number-binding)
- [5. Industrial Safety Interlock](#5-industrial-safety-interlock)
- [6. Station Guard Emergency Override Triple Insurance](#6-station-guard-emergency-override-triple-insurance)
- [7. Practical Integration Code Walkthrough](#7-practical-integration-code-walkthrough)
- [8. Frequently Asked Questions (FAQ)](#8-frequently-asked-questions-faq)

---

## 1. Motivation & Core Challenges

In EMS / ODM electronics manufacturing, test engineers face conflicting requirements between prototype (NPI) and mass production (MP) environments:

| Sequence | [ Manual Test Station (Manual Bench) ] | [ Automated Test Station (Robot / Fixture) ] |
| :---: | :--- | :--- |
| **Step 1** | 1. Operator scans barcode upfront | 1. Conveyor / robot arm places DUT into fixture |
| **Step 2** | 2. Serial number entered into TUI | 2. Robot / pneumatic cylinder clamps chamber |
| **Step 3** | 3. Press Start button to begin | 3. ⚠️ **[Challenge] Barcode inside closed chamber! Cannot scan upfront** |
| **Step 4** | 4. Execute test flow items | 4. **Must start test cycle first; camera/scanner reads SN in-flow** |

<br>

1. **The Sequence Dilemma (Serial Number Chicken-and-Egg)**:
   * Manual benches require the serial number *before* execution starts.
   * Automated dark-box fixtures must clamp and power on the DUT *before* internal cameras or probes can read the serial number.
   * Traditional frameworks force teams to maintain two separate test sequences or branch code with brittle `if/else` logic.
2. **The Pinch-Hazard Dilemma (Remote Actuation Safety)**:
   * When remote engineers SSH into an overseas station PC to debug, executing actuation commands while an on-site operator's hand is inside the fixture causes severe pinching and mechanical injuries.
3. **The Sapas Unified Solution**:
   * **Lazy SN Binding**: A single unified Flow supports both upfront manual scanning and dynamic in-flow hardware barcode binding, with seamless hot-rebinding of loggers and output directories.
   * **Station Trigger IPC**: Provides a clean, lightweight TCP loopback IPC interface for PLCs, robotic arms, and scripts.
   * **Industrial Safety Interlock**: Automatically rejects unlocked remote SSH triggers, alerting remote engineers with high-contrast live telemetry if an operator is actively testing.

---

## 2. System Architecture & Communication Model

Sapas Trigger employs a stateless **Loopback TCP Socket** architecture. The active `SapasDashboard` TUI runs a background server listening on a local loopback port, recording its PID and port token into the user's home directory.

```
+-----------------------------------------------------------------------------------+
|                            Station PC Operating System                            |
|                                                                                   |
|  [ External Clients ]                                                             |
|  • PLC / Robot Arm                                                                |
|  • Local Automation Script ────(send_trigger)───┐                                 |
|  • Remote SSH Session                           │ JSON over TCP                   |
|                                                 ▼ (127.0.0.1:Port)                |
|                                        +------------------+                       |
|                                        |  TriggerServer   | (Background Thread)   |
|                                        +------------------+                       |
|                                                 │                                 |
|                                                 ▼                                 |
|  +-----------------------------------------------------------------------------+  |
|  |                          Active Sapas TUI (PID 11716)                       |  |
|  |                                                                             |  |
|  |   • State Machine: IDLE ──> TESTING ──> PASS/FAIL                           |  |
|  |   • Interlocks   : Station Guard Lock State & Emergency Override Events     |  |
|  |   • Runner Core  : Dynamic Rebinding (Logger + Output Dir + Context)        |  |
|  +-----------------------------------------------------------------------------+  |
|                                                 │                                 |
|                                                 ▼                                 |
|                                       ~/.sapas/tui.ipc                            |
|                                  {"port": 54321, "pid": 11716}                    |
+-----------------------------------------------------------------------------------+
```

### 2.1 State Machine Lifecycle
* **`IDLE`**: Ready and standby for new test triggers.
* **`TESTING`**: Active test execution running; duplicate `start` triggers are rejected with `BUSY`.
* **`LOCKED`**: Station Guard maintenance lock active; local operator controls disabled, remote actuation permitted only for authorized engineers.
* **`EMERGENCY_BRAKE`**: On-site supervisor key override engaged; all automatic and remote triggers are strictly halted.
* **`DEBUG`**: Engineer interactive stepping mode active; automated external triggers blocked.

---

## 3. CLI Command Reference

Sapas provides the `sapas trigger` command suite:

```bash
sapas trigger <command> [options]
```

### 3.1 `sapas trigger start` (Initiate Test)
Sends an execution trigger request to the active Sapas TUI session.

```bash
# Mode A: Lazy SN Mode (Flow scripts dynamically bind serial number)
sapas trigger start

# Mode B: Explicit Upfront Serial Number Mode (Strict lock; script cannot override)
sapas trigger start --sn sapas20261023001
```

#### Exit Codes & Statuses
| Exit Code | Status | Description | Action Required |
| :---: | :--- | :--- | :--- |
| `0` | **`OK`** | Test cycle successfully accepted and started. | Monitor test progress or wait for completion. |
| `2` | **`BUSY`** | Station is currently executing another test cycle. | Wait for the active cycle to finish before retrying. |
| `3` | **`BLOCKED`** | Safety interlock, emergency brake, or lock blocked trigger. | Inspect terminal message (e.g. unlocked SSH trigger). |
| `1` | **`ERROR`** | Communication failure or no active TUI found. | Verify `sapas --tui` is running on the station. |

---

### 3.2 `sapas trigger stop` (Cooperative Abort)
Requests a safe cooperative stop of the active test cycle.

```bash
sapas trigger stop
```
* **Mechanism**: Sets `STOP_REQUESTED = True` in the ExecutionContext. The core [`Runner`](../../sapas/core/runner.py) stops after the current step and executes the `final` block guaranteed teardown (e.g. cutting fixture power, releasing pneumatic clamps).

---

### 3.3 `sapas trigger status` (Live Telemetry)
Queries runtime telemetry from the active TUI session.

```bash
sapas trigger status
```

#### Output Example:
```text
╭────────────── Sapas TUI Status ──────────────╮
│ PID         : 13376                          │
│ State       : TESTING                        │
│ Active SN   : sapas20261023001               │
│ Elapsed     : 32.4s                          │
│ Guard Lock  : UNLOCKED (Local production)    │
╰──────────────────────────────────────────────╯
```

---

## 4. Lazy Serial Number Binding

### 4.1 How It Works
```text
[sapas trigger start] ──> TUI enters Lazy SN mode ──> Temp dir: output/[SCANNING...]/
                                                              │
                                                              ▼
[Execute scan_barcode.py] ──> Hardware barcode read ──> Real SN: "sapas-998877"
                                                              │
                                                              ▼
Call rt.bind_serial_number("sapas-998877")
  1. Context['SERIAL_NUMBER'] updated
  2. Directory renamed seamlessly: output/sapas-998877/20261023_180000/
  3. Runner Logger FileHandler hot-rebound (preserves early log lines)
  4. TUI Header & live dashboard refreshed with real SN
```

### 4.2 Precedence Hierarchy
1. **Upfront Explicit SN (Strict Lock)**:
   * When started with an upfront `--sn`, Sapas sets `_SERIAL_NUMBER_LOCKED = True`.
   * Subsequent script calls to `rt.bind_serial_number()` are ignored with a warning, protecting manual operator scans from rogue script overwrites.
2. **Lazy SN (Dynamic Binding)**:
   * When started with empty SN or `[SCANNING...]`, `_SERIAL_NUMBER_LOCKED = False`.
   * In-flow scripts can bind the official SN once, automatically transitioning to locked mode.

### 4.3 Script Implementation
```python
import sapas
from sapas import TestItem

class ScanBarcode(TestItem):
    def run_test(self):
        # 1. Read serial number from hardware scanner
        scanned_sn = self.read_hardware_scanner()

        # 2. Perform dynamic Lazy SN binding
        sapas.var.set("SERIAL_NUMBER", scanned_sn)
        sapas.info(f"Successfully bound serial number: {scanned_sn}")

        # 3. Store in measurements for Shopfloor / MES evaluation
        sapas.measure.BARCODE = scanned_sn
```

---

## 5. Industrial Safety Interlock

### 5.1 Remote SSH Pinch Hazard Protection
```
[Remote Engineer via SSH] ──> Executes sapas trigger start
                                       │
                                       ▼
                         TUI Inspects Caller Metadata
                                       │
               ┌───────────────────────┴───────────────────────┐
               ▼ (Station Guard UNLOCKED)                      ▼ (Station Guard LOCKED)
       [STATUS_BLOCKED Rejected]                              [Execution Approved]
       • Station TUI plays audible bell                       • Automated cycle runs safely
       • Visual alert on station desktop                      • Operator informed by lock screen
       • High-contrast banner to remote terminal
```

### 5.2 Operator Protection Live Telemetry
If an on-site operator is actively testing a unit when an unauthorized remote trigger arrives, the remote engineer is immediately presented with high-contrast live telemetry:

```text
engineer@remote-pc> sapas trigger start --sn sapas101010101
[BLOCKED] Sapas TUI (PID 22088) rejected trigger:

   [!] ON-SITE TEST IN PROGRESS - FIXTURE OCCUPIED 

  * Current Status :  RUNNING TEST  (Local operator actively testing)
  * Active Serial  : sapas999999999
  * Elapsed Time   : 12.0s

  SAFETY INTERLOCK: Remote trigger via SSH (from 192.168.1.113) is strictly forbidden
  while station is in local production mode without Station Guard lock.

   ATTENTION  DO NOT INTERFERE: An on-site operator is currently working at this fixture.
  Please do NOT interrupt or run 'sapas guard lock' until the ongoing test finishes!
```

---

## 6. Station Guard Emergency Override Triple Insurance

When on-site supervisors use the secret key sequence (`Up Up Down Down Left Right Left Right B A B A`) to unlock the red screen, `override_event.json` is generated.

To prevent stale override markers from falsely tripping subsequent operator tests into `EMERGENCY_STOP`, Sapas employs **Triple Insurance**:

```
[Supervisor Key Override Unlocks Screen] ──> ~/.sapas/override_event.json created
                                                      │
         ┌────────────────────────────────────────────┼────────────────────────────────────────────┐
         ▼                                            ▼                                            ▼
【 Insurance 1: Dialog Exit 】              【 Insurance 2: Local Startup 】             【 Insurance 3: CLI Mode 】
Old TUI presents restart prompt;            Local TUI on_mount initializes;              Local CLI execution starts;
clicking 'Acknowledge & Exit' purges        detects local unlocked session and           clears stale override marker
the override file before exiting.           cleans stale file automatically.             before running test flow.
```

---

## 7. Practical Integration Code Walkthrough

### 7.1 Python PLC / Robot Arm Integration Example
```python
import time
from sapas.trigger import send_trigger, STATUS_OK

def automated_production_cycle():
    # 1. Close pneumatic clamps
    print("Fixture clamped. Sending Sapas start trigger...")

    # 2. Trigger Sapas test in Lazy SN mode
    resp = send_trigger("start")
    if resp.get("status") != STATUS_OK:
        raise RuntimeError(f"Failed to start Sapas: {resp.get('error')}")

    # 3. Poll status until complete
    while True:
        time.sleep(1.0)
        st = send_trigger("status")
        if st.get("state") != "TESTING":
            print(f"Test cycle complete: {st.get('state')}")
            break

    # 4. Open pneumatic clamps
    print("Fixture released.")
```

### 7.2 Sample Flow Configuration (`auto_fixture.flow`)
```yaml
start auto_fixture
    cycle 1
        verify scan_barcode.py
        verify verify_voltage.py --sapas-tag FIRST
        verify get_os_name.py
stop

on_fail
    action sleep.py --sec 1
end

final
    action shopfloor_report.py
end
```

---

## 8. Frequently Asked Questions (FAQ)

### Q1: `Failed to trigger Sapas TUI: No active Sapas TUI session found.`?
**A**: This indicates no active `sapas --tui` process is running. Ensure the TUI is active on the station. If connecting via SSH, verify you are connecting to the correct station IP or hostname.

### Q2: What happens if barcode scanning times out in automated fixtures?
**A**: In `scan_barcode.py`, if hardware scanning times out, record `sapas.measure.BARCODE = "READ_FAIL"` and raise an exception. Sapas's `Runner` immediately aborts the main flow and enters the `final` block, ensuring pneumatic clamps release safely.

### Q3: How can a remote engineer trigger tests for remote debugging?
**A**: Follow standard safety procedure:
1. Lock the station from SSH: `sapas guard lock -m "Remote debugging session"`.
2. Confirm fullscreen red lock engages on the station desktop.
3. Execute `sapas trigger start`. Sapas permits the trigger under active lock.
4. Unlock the station when finished: `sapas guard unlock`.

