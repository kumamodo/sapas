# 05 配置規範 (YAML Configuration)

Sapas 採用多層級的 YAML 配置系統，讓開發者能彈性管理全域環境、專案變數與工位設定。

## 1. 配置層級與優先權

當系統啟動時，會按以下順序載入並合併設定檔。**後者會覆蓋前者的同名變數**：

1.  **`site_infra.yaml`** (全域/環境層級)：定義工廠位置、資料庫連線等不隨專案變更的基礎設施資訊。
2.  **`configs/project.yaml`** (專案層級)：定義該產品專案共用的測試參數、版本號或共用連線。
3.  **`stations/{STATION}/station.yaml`** (工位層級)：定義特定工位的連線資訊（如 IP）、儀器位址等。

---

## 2. 各設定檔存在的意義

### site_infra.yaml (環境基礎設施)
*   **位置**：通常放在工作區根目錄（如 `example/`）。
*   **用途**：跨專案共享的資訊。例如，同一工廠內所有工位都連到同一個 Shopfloor 系統。
*   **典型參數**：`FACTORY_LOCATION`, `ENABLE_SHOPFLOOR`, `DATABASE_IP`。

### project.yaml (專案定義)
*   **位置**：`{Project}/configs/project.yaml`。
*   **用途**：定義該專案的所有工位都會用到的邏輯。例如：韌體預期版本、共用的超時時間。
*   **典型參數**：`EXPECTED_FW_VER`, `TIMEOUT_RETRY`。

### station.yaml (工位硬體)
*   **位置**：`{Project}/stations/{StationName}/station.yaml`。
*   **用途**：定義「這一台機器」特有的資訊。即便是同一個專案，不同工位的 IP 或 COM Port 通常不同。
*   **典型參數**：`link` (連線驅動配置), `STATION_ID`。

---

## 3. 系統核心保留變數

以下是 Sapas 框架內部會引用或自動生成的關鍵參數。請避免將其用於不相關的用途。

| 參數名稱 | 類型 | 說明 |
| :--- | :--- | :--- |
| `PROJECT_NAME` | String | 專案名稱。系統據此尋找對應的資料夾。 |
| `STATION_NAME` | String | 工位名稱。系統據此尋找 `station.yaml` 與預設 `.flow`。 |
| `IS_FAIL_STOP` | Boolean | 若為 `True`，當 `verify` 指令失敗時，會立即中斷測試並跳轉至 `on_fail`。 |
| `link` | Dict | 定義連線驅動（如 SSH）。內部包含 `driver`, `host`, `user` 等子參數。 |
| `WORKSPACE_ROOT`| Path | (系統自動生成) 指向當前執行指令的根目錄。 |
| `ERROR_CODE` | String | (執行時生成) 目前測試狀態。常見值：`PASS`, `FAIL`, `CRITICAL`, `STOP`。 |
| `ERROR_DESCRIPTION`| String | (執行時生成) 失敗時的詳細描述。 |
| `RUNNER_LOGGER` | Object | (系統內部使用) 供 Python 腳本調用的 Logger 物件。 |

---

## 4. 最佳實踐建議

1.  **敏感資訊分離**：將帳號密碼等敏感資訊放在 `site_infra.yaml` 並加入 `.gitignore`，避免提交至代碼庫。
2.  **結構化命名**：建議變數名稱使用全大寫（如 `DUT_IP`），以便在程式碼中一眼看出這是來自 YAML 的設定值。
3.  **預設值定義**：可以在 `project.yaml` 定義一個預設的 `IS_FAIL_STOP: True`，若某個特殊工位需要繼續測試，再在該工位的 `station.yaml` 覆蓋為 `False`。
