# 07 腳本開發參考 (API Reference)

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
... (保留原有的 TestItem 內容) ...

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
        self.info("正在執行系統初始化...")
        ssh = sapas.link.get("DUT")
        ssh.exec("rm -rf /tmp/old_logs")
        self.info("清理完成")

if __name__ == "__main__":
    from sapas.core.user_runner import run_user_script
    run_user_script(__file__)
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

## 3. 變數存取 (sapas.var)

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

## 4. 連線驅動 (sapas.link)

`sapas.link` 用於獲取在 `station.yaml` 中定義的連線物件。

```python
import sapas

def run_test(self):
    # 獲取名為 'DUT1' 的 SSH 連線
    ssh = sapas.link.get("DUT1")
    
    # 執行指令並獲取結果
    result = ssh.exec("uname -a")
    self.info(f"OS Version: {result.stdout}")
```

---

## 5. 日誌輸出

在 `TestItem` 內，推薦使用以下內建方法，日誌會自動帶上 Tag 並保存至檔案。

- **`self.info(msg)`**: 紀錄一般資訊 (Tag: USER)。
- **`self.warn(msg)`**: 紀錄警告資訊 (Tag: WARN)。
- **`self.error(msg)`**: 紀錄錯誤資訊 (Tag: ERROR)。

如果您想在腳本外或全域調用：
```python
import sapas
sapas.info("這是全域日誌")
```

---

## 6. 自定義參數 (@sapas.arg)

如果您需要從 `.flow` 傳遞參數給腳本，可以使用 `@sapas.arg` 裝飾器。

```python
@sapas.arg("--mode", type=str, default="normal", help="測試模式")
class MyTest(sapas.TestItem):
    ...
    def run_test(self):
        # 透過 self.args 存取參數
        current_mode = self.args.mode
        self.info(f"當前模式為: {current_mode}")
```

在 `.flow` 中呼叫方式：
```yaml
verify my_custom_test.py --mode fast
```

---

## 7. 標準腳本模板

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
        self.info("開始執行標準測試...")
        
        # 1. 獲取連線與參數
        ssh = sapas.link.get("DUT")
        limit = self.args.threshold
        
        # 2. 執行動作
        output = ssh.exec("cat /proc/uptime").stdout
        uptime = float(output.split()[0])
        
        # 3. 紀錄量測值 (對應 criteria CSV)
        self.measure.UPTIME = uptime
        self.measure.STATUS = "1" if uptime > limit else "0"
        
        self.info(f"測試完成，Uptime: {uptime}")

if __name__ == "__main__":
    # 支援直接執行腳本進行除錯
    from sapas.core.user_runner import run_user_script
    run_user_script(__file__)
```
