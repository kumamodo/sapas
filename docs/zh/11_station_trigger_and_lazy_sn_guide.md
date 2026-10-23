# 11 外部觸發與延遲序號綁定指南 (Station Trigger & Lazy SN Guide)

`Sapas Station Trigger & Lazy SN` 是專為**自動化產線（Automated Production Line）**、**機器人手臂（Robotic Arm）**、**氣壓自動治具（Pneumatic Fixture）**以及**現代智慧工廠**所設計的自動化控制與工安互鎖子系統。

它徹底打通了**「自動化手臂開測」**與**「現場人工刷條碼開測」**的最後一哩路，並結合 **Station Guard** 構建起嚴密的**工業安全互鎖（Industrial Safety Interlock）**，杜絕遠端工程師誤觸機台夾傷現場作業員的重大工安風險。

---

## 📑 目錄
- [1. 設計背景與核心痛點](#1-設計背景與核心痛點)
- [2. 系統架構與通訊模型 (Architecture)](#2-系統架構與通訊模型-architecture)
- [3. 外部觸發指令手冊 (CLI Reference)](#3-外部觸發指令手冊-cli-reference)
- [4. 延遲序號綁定 (Lazy Serial Number Binding)](#4-延遲序號綁定-lazy-serial-number-binding)
- [5. 工業安全互鎖機制 (Safety Interlock)](#5-工業安全互鎖機制-safety-interlock)
- [6. Station Guard 密技覆寫三重保險 (Emergency Lifecycle)](#6-station-guard-密技覆寫三重保險-emergency-lifecycle)
- [7. 實戰整合範例 (Code Walkthrough)](#7-實戰整合範例-code-walkthrough)
- [8. 常見問題與故障排除 (FAQ)](#8-常見問題與故障排除-faq)

---

## 1. 設計背景與核心痛點

在傳統 EMS / ODM 電子代工廠中，同一款產品在試產（NPI）與量產（MP）時，往往面臨兩難的測試架構衝突：

| 步驟流程 | 【 人工測試站 (Manual Station) 】 | 【 自動化測試站 (Automated Station) 】 |
| :---: | :--- | :--- |
| **Step 1** | 1. 作業員手持條碼槍掃描條碼 | 1. 輸送帶 / 機械手臂送入待測物 (DUT) |
| **Step 2** | 2. 序號先填入軟體畫面 | 2. 手臂 / 氣缸閉合暗箱治具 |
| **Step 3** | 3. 按下按鈕開始測試 | 3. ⚠️ **[痛點] 條碼在閉合暗箱內！無法預先刷碼** |
| **Step 4** | 4. 執行各項電性測試 | 4. **必須先觸發開測通電，內部鏡頭才能讀碼** |

<br>

1. **矛盾一：先有雞還是先有蛋（序號先後順序）**：
   * 人工測試是**「先有 SN 才能開測」**。
   * 自動化治具是**「治具夾進去、在暗箱內通電後，鏡頭或治具探針才能讀到 SN」**。
   * 傳統框架往往被迫維護兩套程式碼，或者寫滿了難以維護的 `if/else` 判斷。
2. **矛盾二：跨國遠端維護的夾手風險（工安隱患）**：
   * 當國外工程師透過 SSH 連進現場電腦排查問題時，若直接下指令觸發治具閉合，現場作業員的手若正好伸在治具內拿取板子，將引發**嚴重的夾手壓傷事故**。
3. **Sapas 的一體化解答**：
   * **Lazy SN Binding**：同一套 Flow，既支援人工預先刷碼，也支援進治具後由腳本動態綁定序號，自動熱轉移 Log 與資料夾。
   * **Station Trigger IPC**：提供輕量非同步 Socket 介面，供手臂、PLC 或腳本精確呼叫。
   * **工安防呆互鎖**：未經現場鎖定（Station Guard）的遠端 SSH 指令一律強制攔截，並提供即時秒數與作業員防干擾警報。

---

## 2. 系統架構與通訊模型 (Architecture)

Sapas Trigger 採用基於 **本機迴路（Loopback TCP Socket）** 的無狀態 IPC 架構，由正在運行的 `SapasDashboard` TUI 在背景監聽本機連接埠，並將狀態與通訊金鑰記錄在使用者家目錄中。

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

### 2.1 狀態機生命週期 (State Machine)
TUI 核心始終處於以下明確定義的狀態之一：
* **`IDLE`**：待機中，隨時接受新一輪測試。
* **`TESTING`**：測試執行中，任何重複的 `start` 請求皆會被拒絕（回傳 `BUSY`）。
* **`LOCKED`**：Station Guard 維護鎖定中，本機作業員無法操作，僅授權工程師可觸發。
* **`EMERGENCY_BRAKE`**：現場主管按密技緊急解鎖，進入全面安全制動，阻斷一切自動開測。
* **`DEBUG`**：工程師單步除錯模式中，阻斷外部自動化開測。

---

## 3. 外部觸發指令手冊 (CLI Reference)

Sapas 提供開箱即用的 `sapas trigger` 子指令集：

```bash
sapas trigger <command> [options]
```

### 3.1 `sapas trigger start`（發起測試）
向當前正在運行的 Sapas TUI 發起啟動測試訊號。

#### 語法與選項
```bash
# 模式 A：延遲序號模式 (Lazy SN Mode)
# 由 Flow 內部腳本 (例如 scan_barcode.py) 動態掃描並綁定序號
sapas trigger start

# 模式 B：顯式序號模式 (Upfront Explicit SN)
# 直接指定序號，鎖定序號優先級，腳本不可篡改
sapas trigger start --sn sapas20261023001
```

#### 回傳代碼 (Exit Codes)
| Exit Code | 狀態字串 | 說明 | 行動建議 |
| :---: | :--- | :--- | :--- |
| `0` | **`OK`** | 測試成功觸發並開始跑測。 | 監控後續狀態或等待測試完成。 |
| `2` | **`BUSY`** | 機台目前正在執行其他測試。 | 等待當前測試結束後再重試。 |
| `3` | **`BLOCKED`** | 工安攔截、緊急煞車、或機台處於鎖定/除錯狀態。 | 檢查終端機詳細提示（例如遠端未鎖定）。 |
| `1` | **`ERROR`** | 通訊失敗、TUI 未啟動或指令無效。 | 確認 `sapas --tui` 是否在背景運行。 |

---

### 3.2 `sapas trigger stop`（協作式停止）
向正在跑測的機台發出停止中斷請求。

```bash
sapas trigger stop
```
* **機制**：不同於作業系統強殺 Process，`trigger stop` 會在 ExecutionContext 標記 `STOP_REQUESTED = True`，核心引擎 [`Runner`](../../sapas/core/runner.py) 在目前測項結束後優雅跳停，並依序執行 `final` 區塊（例如切斷高壓電源、氣缸回位歸零）。

---

### 3.3 `sapas trigger status`（即時狀態遙測）
查詢當前活躍中 TUI 機台的即時狀態看板。

```bash
sapas trigger status
```

#### 輸出範例（執行測試中）：
```text
╭────────────── Sapas TUI Status ──────────────╮
│ PID         : 13376                          │
│ State       : TESTING                        │
│ Active SN   : sapas20261023001               │
│ Elapsed     : 32.4s                          │
│ Guard Lock  : UNLOCKED (Local production)    │
╰──────────────────────────────────────────────╯
```
* **`PID`**：監聽中的 TUI 行程編號。
* **`State`**：目前狀態（`IDLE` / `TESTING` / `LOCKED` / `EMERGENCY_BRAKE`）。
* **`Active SN`**：當前正在測試的產品序號。
* **`Elapsed`**：由 TUI 記憶體以毫秒即時計算出的精確秒數。
* **`Guard Lock`**：機台守護者鎖定狀態。

---

## 4. 延遲序號綁定 (Lazy Serial Number Binding)

### 4.1 核心工作原理
在許多自動化暗箱或治具中，待測物必須先通電或被夾持，內部的掃描槍或攝影機才能辨識標籤。

```text
[sapas trigger start] ──> TUI 進入 Lazy SN 模式 ──> 建立臨時目錄: output/[SCANNING...]/
                                                              │
                                                              ▼
[執行 scan_barcode.py] ──> 讀取掃描槍硬體 ──> 取得真實序號: "sapas-998877"
                                                              │
                                                              ▼
呼叫 rt.bind_serial_number("sapas-998877")
  1. Context['SERIAL_NUMBER'] 更新
  2. 資料夾秒級重新命名: output/sapas-998877/20261023_180000/
  3. Runner Logger FileHandler 熱轉移 (不丟失前半段 log)
  4. TUI 頂部 Header & 儀表板看板同步刷新為真實序號
```

### 4.2 序號優先權原則 (Precedence Hierarchy)
Sapas 實作了嚴格的序號防呆體系：
1. **顯式指定最高優先（Strict Lock）**：
   * 若開測時透過 CLI 給予序號（例如 `sapas --sn X` 或 `sapas trigger start --sn X`），Sapas 會在內部標記 `_SERIAL_NUMBER_LOCKED = True`。
   * 後續腳本呼叫 `rt.bind_serial_number()` 或 `var.set("SERIAL_NUMBER")` 時會被系統忽略並印出保護警告，防止腳本 Bug 誤將手刷條碼覆蓋成垃圾數值。
2. **延遲綁定許可（Lazy SN Dynamic Binding）**：
   * 當測試初始以空序號或 `[SCANNING...]` 啟動時，`_SERIAL_NUMBER_LOCKED = False`。
   * 腳本有且僅有一次機會綁定正式序號。正式序號綁定成功後，系統自動升級為鎖定狀態。

### 4.3 腳本開發語法
在自訂的 `TestItem` 腳本中，只需呼叫 `sapas.var.set("SERIAL_NUMBER", scanned_sn)`：

```python
import sapas
from sapas import TestItem

class ScanBarcode(TestItem):
    def run_test(self):
        # 1. 自硬體讀取條碼 (例如 RS232 / USB 虛擬 COM)
        scanned_sn = self.read_from_scanner_hardware()

        # 2. 進行延遲綁定 (Lazy Binding)
        # Sapas 核心會自動攔截此變數設定，並自動觸發資料夾重命名與日誌熱轉移
        sapas.var.set("SERIAL_NUMBER", scanned_sn)
        sapas.info(f"Successfully bound serial number: {scanned_sn}")

        # 3. 儲存至量測結果供 criteria 與 Shopfloor 比對
        sapas.measure.BARCODE = scanned_sn
```

---

## 5. 工業安全互鎖機制 (Safety Interlock)

### 5.1 遠端觸發防夾手阻擋
為防止遠端工程師在現場人員不知情下誤觸動治具，Sapas 內建通訊環境偵測機制：

```
[遠端工程師透過 SSH] ──> 下達 sapas trigger start
                                │
                                ▼
                     TUI 檢查來源元數據 (Caller Metadata)
                                │
          ┌─────────────────────┴─────────────────────┐
          ▼ (機台未鎖定 Station Guard)                  ▼ (機台已鎖定 sapas guard lock)
  [工安強制拒絕 (STATUS_BLOCKED)]                     [安全核准執行]
  • 現場 TUI 鳴響警笛 (Bell)                        • 治具安全閉合開測
  • 現場印出大紅工安警報                             • 現場螢幕顯示工程維護鎖定中
  • 遠端終端機列出超高對比警報
```

### 5.2 現場作業員防干擾看板
若現場正有一名作業員在機台前手動測試，遠端工程師若在此時下指令，終端機會以**紅底白字置頂警報**呈現機台當前動態，嚴禁遠端人員進行干擾或隨意上鎖：

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

> 🛡️ **防呆核心思維**：遠端工程師看到 `[!] ON-SITE TEST IN PROGRESS` 與秒數時，能立刻知道現場有同仁在測試，絕對不會誤下 `sapas guard lock` 把現場螢幕蓋台。

---

## 6. Station Guard 密技覆寫三重保險 (Emergency Lifecycle)

當遠端維護進行中，若現場發生異常（冒煙、夾料、人員受困），現場主管可輸入秘技（`上上下下左右左右BABA`）進行緊急解鎖（Emergency Override）。

為避免緊急事件留下的 `override_event.json` 誤殺下一輪正常測試，Sapas 設計了嚴密的**三重保險**自動還原機制：

```
[主管密技解鎖大紅畫面] ──> 生成 ~/.sapas/override_event.json
                                   │
      ┌────────────────────────────┼────────────────────────────┐
      ▼                            ▼                            ▼
【 保險一：確認退出時清理 】     【 保險二：本機重開自動清理 】   【 保險三：本機 CLI 測試清理 】
舊 TUI 彈出重開對話框，主管       現場人員直接新開 TUI，啟動      現場人員若以指令模式開測
點擊「Acknowledge & Exit」時      函式 (on_mount) 自動偵測為      (sapas --project ...)，
先刪除檔案再退出應用程式。       本機且無鎖時自動清理檔案。       進入點自動清理殘留檔案。
```

這項保險確保主管重開機台交還給作業員（OP）後，作業員刷條碼即可順暢測試到底，絕不會再出現假警報 `EMERGENCY_STOP`！

---

## 7. 實戰整合範例 (Code Walkthrough)

### 7.1 外部 PLC / 機器人手臂 Python 呼叫範例
若你在自動化機台撰寫 Python 腳本控制機器人手臂與輸送帶，可直接引入 `sapas.trigger` 函式庫：

```python
import time
from sapas.trigger import send_trigger, STATUS_OK, STATUS_BUSY, STATUS_BLOCKED

def automated_production_cycle():
    # 1. 手臂夾持 DUT 放入治具並閉合氣缸
    print("Robot arm placed DUT into fixture. Closing clamps...")
    close_fixture_clamps()

    # 2. 發送 Trigger 觸發 Sapas 開測 (Lazy SN 模式)
    resp = send_trigger("start")
    if resp.get("status") != STATUS_OK:
        raise RuntimeError(f"Failed to start Sapas: {resp.get('error')}")

    print("Sapas test initiated. Polling for completion...")

    # 3. 輪詢機台狀態直到測試完成
    while True:
        time.sleep(1.0)
        st = send_trigger("status")
        if st.get("state") != "TESTING":
            print(f"Test cycle completed! Final state: {st.get('state')}")
            break

    # 4. 釋放氣缸，手臂取出待測物
    open_fixture_clamps()
```

### 7.2 範例 Flow 設定 (`auto_fixture.flow`)
```yaml
# ==============================================================================
# STATION MISSION: Automated Fixture & External Trigger Demo Flow
# Triggered externally via: `sapas trigger start` (Lazy SN mode)
# ==============================================================================

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
    # 保證釋放治具與 Shopfloor 過站
    action shopfloor_report.py
end
```

---

## 8. 常見問題與故障排除 (FAQ)

### Q1: 終端機回傳 `Failed to trigger Sapas TUI: No active Sapas TUI session found.`？
**A**: 代表當前機台沒有正在跑的 `sapas --tui` 行程。請確認現場電腦的 TUI 是否已經啟動。若是透過 SSH 連入，請確認使用的是同一台電腦的主機名稱或 IP。

### Q2: 氣壓治具自動化開測時，條碼槍掃描超時或讀取失敗怎麼辦？
**A**: 在 `scan_barcode.py` 中，如果掃描超時或讀取空值，建議透過 `sapas.measure.BARCODE = "READ_FAIL"` 記錄錯誤並拋出異常，Sapas 的 `Runner` 會立即終止主流程並跳入 `final` 區塊，確保氣缸安全打開，防止產品被鎖死在治具內。

### Q3: 遠端工程師可以透過 `trigger start` 進行調試嗎？
**A**: 可以，但必須**遵循標準安全 SOP**：
1. 遠端工程師在 SSH 輸入：`sapas guard lock -m "Remote debugging session"`。
2. 現場電腦螢幕進入全螢幕大紅鎖定，警示現場人員退開。
3. 此時遠端工程師再執行 `sapas trigger start`，互鎖系統便會認可此授權並允許遠端自動開測。
4. 維護結束後執行 `sapas guard unlock` 解鎖交還機台。

### Q4: 重開機後殘留的 `~/.sapas/tui.ipc` 會不會導致誤判？
**A**: 不會。Sapas 每次讀取 `tui.ipc` 時，都會以 Windows 核心 API（`OpenProcess`）確認該 PID 是否依然存活且為真實的 Sapas 實例。若發現行程早已結束，系統會自動清理陳舊的 IPC 檔案並優雅處理。

