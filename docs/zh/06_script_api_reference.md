# 06 腳本開發參考 (API Reference)

本文件詳細說明在撰寫 Sapas 測試腳本（Python）時可用的 API、類別屬性與裝飾器。

---

## 1. 核心類別：TestItem vs. ActionItem

在 Sapas 中，腳本根據用途分為兩大類：

| 類別 | 用途 | 判定規則 | 必須屬性 |
| :--- | :--- | :--- | :--- |
| **`TestItem`** | 核心測試項 (如電壓測量) | 需比對 CSV 規範，產出 PASS/FAIL | 是 (5個屬性) |
| **`ActionItem`**| 工具類腳本 (如初始化、報表上傳) | 僅看腳本是否崩潰，不需比對 CSV | 否 (不需定義屬性) |

---

## 2. TestItem 開發規範

`TestItem` 是 Sapas 最核心的開發類別，當你在 Flow 中使用 `verify` 指令時，系統預期執行的就是一個 `TestItem`。

### 與 Flow 的互動
當 Flow 執行 `verify my_test.py` 時：
1. **實例化**：系統加載 `TestItem` 並初始化環境。
2. **執行**：呼叫 `run_test()` 方法。
3. **判定**：腳本執行完畢後，`ResultManager` 會根據 `self.measure` 的數據與 `criteria_file` 進行比對。
4. **流控**：若判定結果為 **FAIL**，Flow 會立即中斷並跳轉至 `on_fail` 區塊。

### 必須定義的屬性
為了讓系統自動化處理數據，`TestItem` 必須定義以下五個檔案路徑屬性：
- **`measure_file`**: 暫存量測值的純文字檔名。
- **`result_file`**: 最終判定結果的 CSV 檔名。
- **`criteria_file`**: 比對規範的 CSV 檔名（需位於專案的 `criteria/` 目錄下）。
- **`logs_folder`**: 該測項專屬的日誌資料夾名稱。
- **`logs_name`**: 該測項的日誌檔名。

### 必須實作的方法
- **`run_test(self)`**: 測試邏輯的主入口。在此方法中，你必須透過 `self.measure` 回傳關鍵數據。

### TestItem 標準模板
```python
import sapas

class MyOsTest(sapas.TestItem):
    # 必須定義的 5 個路徑屬性
    measure_file  = "os_check.txt"
    result_file   = "os_check_result.csv"
    criteria_file = "os_check_criteria.csv"
    logs_folder   = "OS_CHECK_LOGS"
    logs_name     = "os_check.log"

    def run_test(self):
        sapas.info("開始檢查作業系統版本...")
        
        # 1. 執行動作 (例如透過 SSH 或本地指令獲取數據)
        # 這裡以獲取系統資訊為例
        raw_output = "Microsoft Windows [Version 10.0.19045.4291]" 
        
        # 2. 處理數據
        extracted_name = "Windows" if "Windows" in raw_output else "Other"
        
        # 3. 紀錄量測值 (名稱 "OS_NAME" 必須存在於 criteria_file 中)
        self.measure.OS_NAME = extracted_name
        
        sapas.info(f"提取的系統名稱為: {extracted_name}")
```
---

## 3. ActionItem 開發規範

`ActionItem` 適用於不需要紀錄測量值，只需執行動作的情況。

### 必須實作的方法
- **`run_action(self)`**: 動作執行的主入口。

### ActionItem 標準模板
```python
import sapas

class SetupSystem(sapas.ActionItem):
    def run_action(self):
        sapas.info("正在執行系統初始化...")
        ssh = sapas.link.get("DUT")
        ssh.exec("rm -rf /tmp/old_logs")
        sapas.info("清理完成")
```

### 開發注意事項
1. **日誌 Tag**: `ActionItem` 的日誌預設 Tag 為 `[ ACTION ]`。
2. **無判定結果**: 它不會產出 `result.csv`，若腳本執行過程中拋出例外，流程會被視為失敗。
3. **用途建議**: 適合用於 `flows` 中的環境設置 (Setup)、結果上傳 (Reporting) 或失敗後的回退處理 (on_fail)。

---

## 4. 數據量測與判定 (self.measure)

`self.measure` 是一個代理物件，讓您能直接將量測值與 `criteria` 中的項目對應。

```python
def run_test(self):
    # 假設 criteria CSV 中有一個測項叫 "CPU_TEMP"
    temp = 45.5
    self.measure.CPU_TEMP = temp  # 自動紀錄量測值
    
    # 假設有一個字串比對測項叫 "OS_NAME"
    self.measure.OS_NAME = "Windows"
```

> **注意**：若您賦值的屬性名稱不在 `criteria_file` 中，系統會立即拋出錯誤。

---

## 5. 變數存取 (sapas.var)

`sapas.var` 用於存取在 `YAML` 設定檔中定義的變數，或在不同腳本間傳遞動態數據。

- **`sapas.var.get(key, default=None)`**: 獲取變數值。
- **`sapas.var.set(key, value)`**: 設置或更新變數值（僅限本次測試循環）。
- **`sapas.var.require(key)`**: 獲取變數，若不存在則拋出例外。

```python
import sapas

def run_test(self):
    # 獲取 YAML 中的設定
    timeout = sapas.var.get("TIMEOUT_RETRY", 10)
    
    # 將本次量測到的 MAC 紀錄到 Context，供後續腳本使用
    sapas.var.set("DUT_MAC", "AA:BB:CC:DD:EE:FF")
```

---

## 6. 連線驅動 (sapas.link)

`sapas.link` 用於獲取在 `station.yaml` 中定義的連線物件。

```python
import sapas

def run_test(self):
    # 獲取名為 'DUT1' 的 SSH 連線
    ssh = sapas.link.get("DUT1")
    
    # 執行指令並獲取結果
    result = ssh.exec("uname -a")
    sapas.info(f"OS Version: {result.stdout}")
```

---

## 7. 日誌輸出

在腳本中，推薦使用 `sapas` 提供之全域日誌函數進行日誌輸出。系統會自動檢測目前執行腳本的上下文（`TestItem` 或 `ActionItem`），自動套用合適的日誌標籤（Tag）並將日誌同時輸出至終端機與對應的日誌檔案中。

- **`sapas.info(msg)`**: 紀錄一般資訊。在 `TestItem` 中顯示標籤為 `[  USER  ]`；在 `ActionItem` 中顯示標籤為 `[ ACTION ]`。
- **`sapas.warn(msg)`**: 紀錄警告資訊 (Tag: `[  WARN  ]`)。
- **`sapas.error(msg)`**: 紀錄錯誤資訊 (Tag: `[ ERROR  ]`)。

```python
import sapas

class LogDemo(sapas.ActionItem):
    def run_action(self):
        sapas.info("這是一條一般資訊日誌")
        sapas.warn("這是一條警告日誌")
        sapas.error("這是一條錯誤日誌")
```

---

## 8. 內建延遲 (sapas.sleep)

為了避免使用 Python 原生的 `time.sleep()` 導致日誌時間不透明，Sapas 提供了內建的延遲功能：

- **`sapas.sleep(seconds)`**: 延遲指定的秒數（支援整數與浮點數），並在終端機或 TUI 中顯示即時倒數計時。

```python
import sapas

class SleepDemo(sapas.ActionItem):
    def run_action(self):
        sapas.info("準備發送 Shopfloor 數據...")
        # 延遲 5.5 秒，會在 Log 中輸出倒數資訊，避免畫面凍結
        sapas.sleep(5.5)
        sapas.info("數據發送成功")
```

執行此腳本時，會自動在 Log 中輸出如下內容：
```text
[ ACTION ] [DELAY] Sleep for 5.5 seconds.
[ ACTION ] [DELAY] Countdown 6 sec...
[ ACTION ] [DELAY] Countdown 5 sec...
[ ACTION ] [DELAY] Countdown 4 sec...
[ ACTION ] [DELAY] Countdown 3 sec...
[ ACTION ] [DELAY] Countdown 2 sec...
[ ACTION ] [DELAY] Countdown 1 sec...
[ ACTION ] [DELAY] Countdown 0.5 sec...
[ ACTION ] [DELAY] Sleep finished.
```

---

## 9. 自定義參數 (@sapas.arg)

如果您需要從 `.flow` 傳遞參數給腳本，可以使用 `@sapas.arg` 裝飾器。

```python
@sapas.arg("--mode", type=str, default="normal", help="測試模式")
class MyTest(sapas.TestItem):
    ...
    def run_test(self):
        # 透過 self.args 存取參數
        current_mode = self.args.mode
        sapas.info(f"當前模式為: {current_mode}")
```

在 `.flow` 中呼叫方式：
```yaml
verify my_custom_test.py --mode fast
```

---

## 10. 標準腳本模板

```python
import sapas
import sys

@sapas.arg("--threshold", type=float, default=50.0)
class StandardTest(sapas.TestItem):
    measure_file  = "std_measure.txt"
    result_file   = "std_result.csv"
    criteria_file = "std_criteria.csv"
    logs_folder   = "STD_LOGS"
    logs_name     = "std.log"

    def run_test(self):
        sapas.info("開始執行標準測試...")
        
        # 1. 獲取連線與參數
        ssh = sapas.link.get("DUT")
        limit = self.args.threshold
        
        # 2. 執行動作
        output = ssh.exec("cat /proc/uptime").stdout
        uptime = float(output.split()[0])
        
        # 3. 紀錄量測值 (對應 criteria CSV)
        self.measure.UPTIME = uptime
        self.measure.STATUS = "1" if uptime > limit else "0"
        
        sapas.info(f"測試完成，Uptime: {uptime}")
```
---

## 11. 腳本偵錯方式

為了確保腳本在 Sapas 環境下正確運行，**不建議**直接使用 `python script.py` 執行。請統一使用 Sapas 提供的 CLI 指令進行偵錯：

```bash
# 偵錯單一腳本
sapas <腳本名稱>
```

這樣系統會自動加載對應的 YAML 設定與連線資訊，模擬最真實的執行環境。

