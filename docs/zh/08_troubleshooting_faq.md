# 08 故障排除與 FAQ (Troubleshooting)

本文件列出了在使用 Sapas 框架時可能遇到的常見錯誤、其原因以及解決方法。

---

## 1. 啟動與配置問題

### Q: 出現 `[Error] Project or Station not specified!`
- **原因**：執行 `sapas` 時沒有帶 `--project` 或 `--station` 參數，且 `site_infra.yaml` 中也沒有定義預設值。
- **解決**：
  1. 在指令中加入參數：`sapas --project Alishan --station Function`。
  2. 或在 `site_infra.yaml` 中加入 `PROJECT_NAME` 與 `STATION_NAME`。

### Q: 出現 `Station config not found: .../station.yaml`
- **原因**：系統在您指定的專案路徑下找不到對應的工位設定檔。
- **解決**：檢查目錄結構，確保路徑為 `{Project}/stations/{Station}/station.yaml`。請注意大小寫必須完全一致。

### Q: 變數出現 `Required variable '...' not found.`
- **原因**：腳本調用了 `sapas.var.require()` 但該變數未在任何 YAML 中定義。
- **解決**：檢查 `site_infra.yaml`, `project.yaml` 或 `station.yaml` 是否漏掉了該變數。

---

## 2. 流程與腳本執行問題

### Q: 出現 `Script not found: my_script.py`
- **原因**：在 `.flow` 檔案中指定的腳本名稱無法在專案的 `scripts/` 目錄下找到。
- **解決**：確保腳本副檔名為 `.py` 且放置在正確的 `scripts/` 資料夾中。

### Q: 測試結果顯示 `Exception`
- **原因**：Python 腳本執行時崩潰（Runtime Error），導致沒有正常上傳量測值。
- **解決**：查看日誌（Log）中的 Traceback 資訊，定位腳本哪一行出錯。常見原因包括空值處理不當或除以零。

### Q: 為什麼 `if` 條件判斷失效？
- **原因**：Sapas 的 `if` 目前僅支援 `==` 語法且兩邊會轉換為字串比對。
- **解決**：確保 YAML 中的變數值與 `.flow` 中的比對值完全一致。例如 `if ENABLE == True` 在 YAML 中若寫成 `ENABLE: true` (小寫)，比對可能會失敗。

---

## 3. 連線與驅動問題

### Q: SSH 連線失敗：`Failed to connect to ...`
- **原因**：網路不通、IP 錯誤、帳號密碼不對，或目標機台未開啟 SSH 服務。
- **解決**：
  1. 使用手動工具（如 PuTTY 或 `ssh` 指令）確認是否能連線。
  2. 檢查 `project.yaml` 中的 `link` 配置。

### Q: SFTP 上傳/下載出錯
- **原因**：權限不足（Permission Denied）或遠端目錄不存在。
- **解決**：確保遠端路徑具備寫入權限，或先使用 `ssh.exec("mkdir -p ...")` 建立目錄。

---

## 4. 判定與結果問題

### Q: 出現 `Test item does not exist in the CSV.`
- **原因**：您在腳本中使用 `self.measure.ITEM_A = 10`，但對應的 `criteria_file` (CSV) 中沒有 `ITEM_A` 這一行。
- **解決**：在 CSV 檔案中新增對應的測項名稱，並確保拼字與大小寫一致。

### Q: 為什麼所有測項結果都是 `NA`？
- **原因**：腳本執行成功，但可能完全沒有呼叫到 `self.measure` 進行賦值。
- **解決**：檢查腳本邏輯，確保每個測試路徑都有對應的量測值上傳。

---

## 5. 其他環境問題

### Q: Windows 終端機日誌出現亂碼
- **原因**：Windows 預設編碼並非 UTF-8。
- **解決**：Sapas 已內建編碼處理，但建議將終端機（如 CMD 或 PowerShell）切換至 UTF-8 模式，或使用 VS Code 內建的終端機。

### Q: 如何調整超時時間 (Timeout)？
- **解決**：在調用 `ssh.exec(command, timeout=5)` 時可以傳入 `timeout` 參數。若要全域調整，建議在 `project.yaml` 定義一個變數供所有腳本引用。
