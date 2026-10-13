# 10 Station Guard & Remote Maintenance Guide

`Sapas Station Guard` is an **active industrial safety interlock and remote maintenance system** engineered specifically for factory production lines and automated test stations.

In modern smart manufacturing environments, remote R&D (RD) and test engineers frequently connect to on-site or overseas stations via SSH for remote debugging, calibration, or test script execution. The core missions of Station Guard are:
1. **Physical Safety Protection**: Forcefully pop up a fullscreen, topmost red alert window and lock desktop input focus on the station display during remote maintenance, preventing on-site operators from touching machinery, high voltages, or moving fixtures unaware.
2. **Shopfloor Data Protection**: Force `ENABLE_SHOPFLOOR=False` during remote test runs to prevent debug data from contaminating official MES databases.
3. **Emergency Interlock & Safe Exit**: Provide a secure, authorized on-site override mechanism that triggers an immediate "emergency brake" on any active remote test script if locally overridden.

---

## Table of Contents
- [1. Architecture & Safety Mechanisms](#1-architecture--safety-mechanisms)
- [2. CLI Command Reference](#2-cli-command-reference)
- [3. Station Commissioning SOP](#3-station-commissioning-sop)
- [4. Remote Maintenance Workflow](#4-remote-maintenance-workflow)
- [5. Windows Session 0 Isolation & Remote Reboot](#5-windows-session-0-isolation--remote-reboot)
- [6. On-Site Emergency Override Procedure](#6-on-site-emergency-override-procedure)
- [7. Remote Connection Safety Policies](#7-remote-connection-safety-policies)
- [8. Troubleshooting & FAQ](#8-troubleshooting--faq)

---

## 1. Architecture & Safety Mechanisms

Station Guard operates through three coordinated layers:

```
+-------------------------------------------------------------+
|                      Remote Engineer                        |
|  (SSH Client / 192.168.1.113: Session 0 Background Console) |
+-------------------------------------------------------------+
                              |
       sapas guard lock       |   (SSH Execution / Auto-guard)
                              v
+-------------------------------------------------------------+
|                   Sapas State Engine (~/.sapas)             |
|       [.station_lock]  <--->  [override_event.json]         |
+-------------------------------------------------------------+
         ^                                            ^
         | Polling / Event                            | Emergency Brake
         v                                            v
+-----------------------------------+     +-------------------+
|    Station Guard Daemon (Win32)   |     | Sapas Test Engine |
|     (Session 1 Desktop Window)    |     | (Runner / TUI)    |
|   * Fullscreen Red Topmost Window |     | * Force SF=False  |
|   * Audio Alarm (winsound)        |     | * Purple UI Border|
|   * Focus Snatch & Mouse Trap     |     | * Emergency Halt  |
+-----------------------------------+     +-------------------+
```

- **Station Guard Daemon**: A lightweight process resident in the active Windows desktop (Session 1). It continuously monitors lock states, immediately popping up a fullscreen red alert window and playing audio alerts when engaged.
- **State Engine (Lock Manager)**: Manages atomic file operations on `~/.sapas/.station_lock` and `override_event.json` across processes and networks.
- **Runtime Interlock**: During script execution, automatically overrides Shopfloor settings and enforces safety brakes upon detecting remote SSH sessions.

---

## 2. CLI Command Reference

```bash
sapas guard <subcommand> [options]
```

| Command | Description | Intended For |
| :--- | :--- | :--- |
| `sapas guard lock "message"` | Engage maintenance lock (blocks local input & alerts desktop) | Remote RD / Maintenance |
| `sapas guard unlock` | Release maintenance lock and restore normal station operation | Remote RD / Maintenance |
| `sapas guard status` | Check guard daemon health, auto-run status, and active locks | Everyone |
| `sapas guard install` | Register Station Guard into Windows Startup folder and launch daemon | On-site Commissioning / Remote Setup |
| `sapas guard reinstall` | Reset all lock states, clean install, and restart background daemon | Maintenance & Troubleshooting |
| `sapas guard uninstall` | Stop daemon, remove startup shortcut, and purge all guard states | System Removal |

---

## 3. Station Commissioning SOP

When a newly assembled test station is configured with Sapas, perform a one-time commissioning setup.

### Option A: Local Installation on Station PC (Recommended)
1. Log into the station Windows desktop and open a terminal (PowerShell or CMD).
2. Navigate to the Sapas directory and execute:
   ```cmd
   sapas guard install
   ```
3. A Security Notice panel will appear:
   - User-level startup item only — **requires NO administrator or UAC privileges**.
   - Zero registry, system core, or driver modifications.
4. Enter `Y` to confirm.
5. The daemon will start immediately in the background and will launch automatically on every future Windows boot into the desktop.

> [!TIP]
> In automated deployment scripts or CI/CD pipelines, pass `-y` to skip prompts:
> `sapas guard install -y`

---

## 4. Remote Maintenance Workflow

Standard operating procedure (SOP) when an engineer connects remotely via SSH:

### Step 1. Connect via SSH
```bash
ssh tester@192.168.1.100
```

### Step 2. Engage Station Maintenance Lock
Before modifying hardware or running tests, engage the lock with a descriptive message (quotes recommended):
```bash
sapas guard lock "Replacing RF cable & running calibration"
```
- **Lock Engaged**: The terminal displays the red `[!] [LOCKED]` panel. The station physical screen is instantly blanketed by a fullscreen red alert showing your IP, timestamp, and message.
- **Fail-Fast Safety Check**: If the station PC is **not running the Guard Daemon**, the system **rejects the lock** and presents clear remedy options (see Section 5), preventing false-positive security assumptions.

### Step 3. Execute Debugging & Test Scripts
Navigate to your test folder and run test scripts or launch TUI normally:
```bash
sapas rf_test.py
# or
sapas --tui
```
Sapas automatically enforces `ENABLE_SHOPFLOOR=False` to prevent test data from reaching MES.

### Step 4. Release Lock upon Completion
Once maintenance is complete, release the lock:
```bash
sapas guard unlock
```
The red fullscreen window closes automatically, returning desktop control to line operators.

---

## 5. Windows Session 0 Isolation & Remote Reboot

### What is Session 0 Isolation?
Windows isolates system services (including the OpenSSH server `sshd.exe`) within **Session 0**, while interactive user desktops run in **Session 1 or higher**.

When connected via SSH:
- Your terminal executes inside Session 0 (headless, non-interactive environment).
- If the Station Guard daemon was not running prior to connection, GUI windows spawned from SSH cannot render on the physical monitor.

### Two Remedy Routes on Lock Failure

If `sapas guard lock` fails due to an absent daemon, choose between two clear paths:

```text
Remedy Options:
  • Option 1: On-site Setup (Instant / No Reboot)
    Ask an on-site engineer to run locally on the station PC:
      sapas guard install
    (Takes effect immediately without rebooting)

  • Option 2: Remote Setup via SSH (Requires Station Reboot)
    1. Run installation in this SSH session:
       sapas guard install
    2. Reboot the station PC remotely:
       shutdown /r /t 0
       (Windows automatically starts the daemon into Session 1 upon boot)
```

> [!IMPORTANT]
> `shutdown /r /t 0` is the standard Windows command to reboot immediately (`/r` for reboot, `/t 0` for 0 seconds delay). The SSH session will disconnect. Reconnect in 30~60 seconds after Windows desktop logs in.

---

## 6. On-Site Emergency Override Procedure

What happens if an on-site situation occurs (e.g. equipment jam, emergency, or remote engineer lost connection while locked)?

### 1. Line Operators (OP) Policy
- **Never attempt to force-shutdown or tamper with the station**.
- Look at the screen: **Client IP** and **Reason** are clearly displayed.
- Notify the line supervisor or message the engineer on Teams / WeChat.
- In immediate physical danger, push the hardware **Emergency Stop (E-Stop)** button.

### 2. Authorized Supervisors (PE/TE) Override Sequence
If remote personnel cannot be contacted and on-site recovery is authorized, a supervisor can dismiss the screen using the **Supervisor Key Sequence**:

1. Step up to the station keyboard.
2. Enter the sequence within a rolling **10-second** window:
   $$\uparrow \quad \uparrow \quad \downarrow \quad \downarrow \quad \leftarrow \quad \rightarrow \quad \leftarrow \quad \rightarrow \quad \text{b} \quad \text{a} \quad \text{b} \quad \text{a}$$
   *(Up, Up, Down, Down, Left, Right, Left, Right, b, a, b, a)*
3. The red screen closes instantly, restoring desktop control.

### 3. Emergency Brake Interlock
To protect personnel from concurrent remote testing commands, an override event (`override_event.json`) is logged immediately:
- **Remote Test Halt**: Any running remote test script immediately halts (`Exit 1`), printing:
  ```text
  [!] [DANGER] STATION WAS FORCEFULLY UNLOCKED ON-SITE!
      Local personnel used Emergency Override Sequence.
      Aborting all testing to protect on-site personnel safety.
  ```
- **Station TUI Restart Modal**: If Sapas TUI is running locally, it switches to a modal prompting confirmation before continuing.

---

## 7. Remote Connection Safety Policies

When Sapas detects a remote SSH session:

1. **Mandatory Shopfloor Deactivation (`ENABLE_SHOPFLOOR=False`)**:
   - Even if YAML specifies `ENABLE_SHOPFLOOR: true`, the runtime context forcefully overrides it to `False`.
   - Clear warnings are emitted to logs, guaranteeing debug data never pollutes MES.
2. **Neon Purple TUI Safety Border**:
   - Remote TUI renders with a steady **neon purple border** labeled:
     `🌐 REMOTE (192.168.1.113) | SHOPFLOOR DISABLED`
   - Border blinking is disabled to prevent latency lag and visual fatigue over SSH.
3. **Auto-Guard Interlock**:
   - If an engineer executes a test script remotely without manually engaging `sapas guard lock`, Sapas automatically locks the station in the background.

---

## 8. Troubleshooting & FAQ

### Q1: Why does `sapas guard lock` error out saying Daemon is not running?
**A**: The station PC has not installed the startup script or has not logged into the desktop yet. Follow terminal instructions: run `sapas guard install` and reboot with `shutdown /r /t 0`.

### Q2: On multi-monitor station PCs, does the red lock cover all displays?
**A**: The window covers the Windows Primary Display and captures focus so background windows cannot receive clicks or keystrokes. For multi-monitor stations, ensure instrumentation tools are hosted on the primary display.

### Q3: What does `sapas guard uninstall` clean up?
**A**:
1. Terminates all active guard daemon processes.
2. Deletes `SapasStationGuard.vbs` from the Windows Startup folder.
3. Purges `.station_lock`, `override_event.json`, and `guard.pid` from `~/.sapas/`.

### Q4: Daemon does not start after station reboot?
**A**:
1. Ensure the Windows user account is configured with **Auto-login**. Startup programs launch upon desktop login (Session 1).
2. Run `sapas guard status` to verify `Startup Auto-Run` is `Installed`. If not, re-run `sapas guard install`.
