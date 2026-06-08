⚠️ **Active Development Notice** This project is under active development. APIs and internal structures may evolve as we continuous align cross-team requirements.

# Sapas
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
![Open Source](https://img.shields.io/badge/Open%20Source-%E2%9D%A4-brightgreen)
![Price](https://img.shields.io/badge/Price-100%25%20Free-blue)

> **Sapas** /sa'paʃ/ — Inspired by the phrase for *"Bravo! Well done!"* Our goal is simple: when a test flow transits from design to factory, it just **PASS**.

A unified test automation platform bridging the gap between RD hardware verification and factory production testing.

---

### 🎉 100% Free & Open Source 
**sapas** is completely free and open-source under the MIT license! You can freely clone it, modify it, and use it in your personal projects or commercial factory production lines without any cost.

![Sapas Interactive TUI Dashboard](./docs/images/tui_screenshot.png)

## The Problem It Solves: The Cross-Team Fragmentation

In the lifecycle of product development, a destructive cycle often occurs:

1. **RD (Research & Development)** writes their own validation scripts in the lab to bring up the hardware.
2. **TE (Test Engineering)** re-writes completely different automation blocks to fit their test equipment.
3. **PE (Production/Manufacturing)** struggles to deploy a frankenstein framework on the shop floor, resulting in untraceable bugs and heavy maintenance overhead.

**Sapas** is built to break this silo. It is NOT just another "high-performance" runner; it is a **unified testing platform** designed to be the single source of truth from the engineering lab to the continuous assembly line.

---

## Core Philosophy: Unified Architecture

Sapas provides a clean abstraction layer that allows RD, TE, and Factory operators to speak the exact same language:

* **For RD (Lab Verification)**: It acts as a structured environment to write modular `TestItem` blocks using standard protocols (SSH, ADB, UART) without worrying about factory databases or UI rendering.
* **For TE (Deployment & Criteria)**: It separates test logic from standard criteria. TE can shift test limits or sequencing via dynamic configuration files (YAML/CSV) without touching the core code written by RD.
* **For Factory Control (Station Loop)**: It wraps everything into a robust, operator-friendly CLI/TUI environment. It handles continuous looping, serial number inputs, and data hygiene automatically.

---

## Why Sapas?

* \*\*Bridge the Gap\*\*: Stop re-writing scripts. The exact same Python code written during early validation can be directly deployed onto the production line.**Bridge the Gap**: Stop re-writing scripts. The exact same Python code written during early validation can be directly deployed onto the production line.
* **Separation of Concerns**:
  * **RD** controls the **Logic** (How to interact with the device).
  * **TE** controls the **Criteria & Sequence** (What defines a PASS/FAIL and in what order).
  * **Sapas Engine** controls the **Infrastructure** (Logs, UI, data convergence, and hardware connection pools).
* **Defensive by Design**: Implements strict data normalization (e.g., rigid boolean convergence) and contract checking (`opas.var.require`) to prevent laboratory scripts from breaking under harsh factory environments.
* **Aesthetic & Noise-Free CLI**: A unified terminal output powered by `rich`, using balanced visual markers (`✓` / `❌`) ensuring that field technicians can instantly read station health without parsing through raw text noise.

---

* **Aesthetic & Noise-Free CLI**: A unified terminal output powered by `rich`, using balanced visual markers (`✓` / `❌`) ensuring that field technicians can instantly read station health without parsing through raw text noise.

---

## 🌐 Documentation / 說明文件

Explore the full guides in your preferred language:

* 🇺🇸 **[English Documentation](./docs/en/README.md)**
  * [Quick Start](./docs/en/01_quick_start.md) | [Architecture](./docs/en/02_architecture.md) | [Station Loop Mode](./docs/en/07_how_to_build_a_station.md)
* 🇹🇼 **[繁體中文說明文件](./docs/zh/README.md)**
  * [快速開始](./docs/zh/01_quick_start.md) | [架構設計](./docs/zh/02_architecture.md) | [生產線站點部署](./docs/zh/07_how_to_build_a_station.md)

---

## Core Concepts

* **Sequence-Driven Framework**: Test paths are decoupled from implementation. Sequences are orchestrated via configuration files, allowing rapid updates on the shop floor.
* **Unified Result Manager**: Eliminates fragmentation in telemetry. Every single test module feeds into a standardized data model, ensuring tracking stability across all shifts.
* **Multi-Protocol Link Layer**: Built-in support for standard engineering interfaces (**ADB**, **UART**, and **SSH**) so teams don't reinvent connection wrappers.

---

## Installation & Getting Started

To install or update Sapas in editable mode for cross-team development (this automatically updates dependencies such as \`textual\`):To install Sapas in editable mode for cross-team development:

```bash
# 1. Clone the repository and install Sapas
git clone [https://github.com/kumamodo/sapas.git](https://github.com/kumamodo/sapas.git)
cd sapas
pip install -e .

# 2. Go to the example project folder (CRITICAL!)
cd example/

# 3. Run the automation platform (Choose one mode below)
# Mode A: Standard CLI Mode
sapas --project Alishan --station Function

# Mode B: Interactive TUI Dashboard (Recommended for Stations)
sapas --project Alishan --station Function --tui
```

## Factory/Station Deployment (Recommended)

Alternatively, to avoid typing long arguments, you can pre-define your target environment inside `site_infra.yaml`:

```yaml
# site_infra.yaml (Example for Alishan)
PROJECT_NAME: Alishan
STATION_NAME: Function
```

Once this file is set up, simply navigate to that project directory (`example/`) and execute the bare command:Execute `sapas` in your project root. See the `Alishan` example for a complete demonstration.

```bash
sapas
# or for TUI dashboard
sapas --tui
```

## Advanced Development & Debugging

Single-Step Script Execution (Isolated Testing)

During development or factory-line debugging, you do not need to run the entire station testing loop just to verify a single modification. \*\*Sapas\*\* allows you to execute any individual \`TestItem\` or \`ActionItem\` script independently right from your project root directory.  Simply open your terminal at the project root and pass the filename directly to the \`sapas\` CLI:

```bash
sapas get_os_name.py
```
