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

## 程式碼開發守則

在 `example/Alishan/scripts/` 中的腳本（如 `demo_logs.py`）遵循以下原則：

1.  **測量值回傳**: 透過 `sapas` 提供的 API 將數據傳遞給 `ResultManager`。
2.  **結果收斂**: 
    - 成功或通過：回傳 `1` 或 `Y`。
    - 失敗或不通過：回傳 `0` 或 `N`。
3.  **大寫命名**: 測項名稱一律使用大寫蛇形命名法。

## 數據處理流程

1. `Runner` 啟動 `function.flow`。
2. 腳本 `get_os_name.py` 執行並產出測量值 `Windows`。
3. `ResultManager` 讀取 `get_os_name_criteria.csv`。
4. 比對 `Measured (Windows)` 是否等於 `LSL (Windows)`。
5. 生成最終報告並標記為 `PASS`。
