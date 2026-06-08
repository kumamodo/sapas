# 04 資料規範 (Criteria Format)

為了實現自動化判定，Sapas 使用 CSV 格式的 Criteria 來定義規範。請參考 `example/Alishan/criteria/`。

## Criteria CSV 格式範例

以 `Function` 站點會用到的 `get_os_name_criteria.csv` 為例：

| Test Item | LSL | USL | Measured | Status | Description | ErrCode |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| OS_NAME | Windows | Windows | | | 檢查作業系統是否為 Windows | E101 |
| CPU_SERIAL | RECORD | RECORD | | | 紀錄 CPU 序號 | |

### 判定規則：
- **數值比對**: 若 `LSL` 與 `USL` 為數字，系統會檢查測量值是否在範圍內。
- **字串比對**: 若 `LSL == USL` 且為字串，則進行精確匹配。
- **RECORD**: 不論測量值為何，結果皆為 PASS，僅作數據紀錄。
- **ErrCode**: 失敗時產生的錯誤碼。支援 `CodeLow:CodeHigh` 格式。

## 測量與判定流程 (Measurement & Validation Flow)

Sapas 將腳本開發與自動判定緊密結合。以下是從開發到產出結果的完整流程：

1.  **腳本開發原則**：
    *   **大寫命名**：測項名稱 (Test Item) 在程式碼與 CSV 中一律使用大寫蛇形命名法 (如 `OS_NAME`)。
    *   **數據回傳**：腳本執行期間，透過 `sapas` API 將數據傳遞給 `ResultManager`。

2.  **自動化處理步驟**：
    *   **啟動**：`Runner` 啟動 `.flow` 檔案中的指令。
    *   **執行**：腳本 (如 `get_os_name.py`) 執行並產出測量值 (如 `Windows`)。
    *   **加載**：`ResultManager` 自動讀取對應的 Criteria CSV (如 `get_os_name_criteria.csv`)。
    *   **比對**：系統將測量值與 CSV 中的 `LSL/USL` 進行比對。
    *   **報告**：判定結果 (PASS/FAIL)，紀錄狀態並生成最終測試報告。

