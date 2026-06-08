# 07 快速建站指南 (Station Setup)

本指南將帶領您從零開始，在現有的專案（以 `Alishan` 為例）中建立一個全新的測試站別。

## 建立站別的四大步驟

假設我們要建立一個名為 `Final_Check` 的新站別，請遵循以下步驟：

### 第一步：建立工位資料夾與設定
在 `stations/` 目錄下建立與站別同名的資料夾，並放入 `station.yaml`。
- **路徑**：`example/Alishan/stations/Final_Check/station.yaml`
- **內容**：定義該機台特有的連線資訊。
  ```yaml
  # station.yaml 範例
  STATION_LOCATION: FA
  FIXTURE_ID: 002

  PSU_COM_PORT: COM9
  PSU_BAUDRATE: 9600

  FIXTURE_PLC_TYPE: SOCKET
  FIXTURE_PLC_SOCKET_PORT: 5001
  FIXTURE_CTL_SOCKET_PORT: 5002
  TUI_SOCKET_PORT: 2003

  NOISE_SENSOR_COM_PORT: COM25
  NOISE_SENSOR_BAUDRATE: 9600
  ```

### 第二步：定義測試流程 (Flow)
在 `flows/` 目錄下建立 `.flow` 檔案。建議檔名與站別一致。
- **路徑**：`example/Alishan/flows/final_check.flow`
- **內容**：使用 `verify` 或 `action` 串接您的測試腳本。
  ```yaml
  start final_check
      cycle 1
          action demo_logs.py
          verify get_os_name.py
          # 您可以在這裡加入更多自定義腳本
  stop
  
  on_fail
      action sleep.py --sec 2
  end
  ```

### 第三步：準備測試腳本 (Scripts)
將您的 Python 測試邏輯放在 `scripts/` 目錄下。
- **路徑**：`example/Alishan/scripts/my_custom_test.py`
- **重點**：
  - 使用 `sapas.var.get()` 讀取設定。
  - 使用 `measure.add()` 紀錄測試結果。

### 第四步：設定判定規範 (Criteria)
在 `criteria/` 目錄下建立與腳本對應的 CSV 規範檔案。
- **路徑**：`example/Alishan/criteria/my_custom_test_criteria.csv`
- **內容**：定義測項名稱、上下限 (LSL/USL) 與錯誤碼。

---

## 如何執行新站別？

完成上述步驟後，切換到工作目錄並執行：

```bash
cd example
sapas --project Alishan --station Final_Check
```

系統會自動尋找：
1. `stations/Final_Check/station.yaml` 載入設定。
2. `flows/final_check.flow` 執行流程。

---

## 常見問題 Q&A

**Q: 我的測試腳本可以放在專案資料夾外面嗎？**
---
A: 建議放在專案內的 `scripts/` 目錄以便管理。

**Q: 為什麼我的新腳本執行了，但沒看到判定結果？**
---
A: 請檢查：
1. `criteria/` 下是否有對應的 CSV 檔案。
2. CSV 中的測項名稱是否與腳本中上傳的一致（注意大小寫）。
