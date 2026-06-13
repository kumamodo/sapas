# 05 配置規範 (YAML Configuration)

Sapas 採用多層級的 YAML 配置系統，讓開發者能彈性管理全域環境、專案變數與工位設定。

## 1. 配置層級與優先權

當系統啟動時，會按以下順序載入並合併設定檔。**後者會覆蓋前者的同名變數**，這意味著最細節的「工位設定」擁有最高優先權：

1.  **`site_infra.yaml`** (全域/環境層級)
2.  **`configs/project.yaml`** (專案層級)
3.  **`stations/{STATION}/station.yaml`** (工位層級)

**優先權範例**：
`stations/Function/station.yaml` > `configs/project.yaml` > `site_infra.yaml`

**應用場景**：
假設在 `site_infra.yaml` 中定義了 `FACTORY_LOCATION: Chiayi`。
*   在 `function.flow` 中，你可以直接使用這個變數進行邏輯判斷。
*   在 Python 腳本中，也可以透過 API 存取。

---

## 2. 變數存取介面：sapas.var

在 Sapas 框架中，所有合併後的設定以及執行期間動態產生的數據，都被視為「全域變數」。不論是在 **Python 腳本 (Script)** 還是 **測試流程 (Flow)** 中，都可以透過 `sapas.var` 進行存取或寫入。

### 存取與寫入方式：
*   **讀取變數**：使用 `sapas.var.get("KEY_NAME")`。
*   **寫入/更新變數**：使用 `sapas.var.set("KEY_NAME", value)`。

這使得 `sapas.var` 成為一個強大的全域數據中樞，方便在不同的測試步驟之間傳遞資訊（例如：在步驟 A 存入量測值，在步驟 B 根據該值進行判斷）。

---

## 3. 各設定檔存在的意義

### site_infra.yaml (環境基礎設施)
*   **位置**：通常放在工作區根目錄（如 `example/`）。
*   **用途**：跨專案共享的資訊。例如，同一工廠內所有工位都連到同一個 Shopfloor 系統。
*   **典型參數**：`FACTORY_LOCATION`, `ENABLE_SHOPFLOOR`, `SMB_SERVER_IP`。

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
| `IS_EXCEPTION_STOP` | Boolean | 若為 `True`，當腳本拋出異常或崩潰（非 `80` 錯誤碼）時，會立即中斷測試。設為 `False` 可在開發時搭配 `IS_FAIL_STOP` 做完整測試。 |
| `ENABLE_SHOPFLOOR`| Boolean | 表示當前測試是否連接 Shopfloor。 |
| `ENABLE_SMB` | Boolean | 是否將測試過程中的 Log 與數據 (通常為 `output/{序號}`) 上傳至 Server 以供日後追蹤。 |
| `LINK` | Dict | 定義連線驅動（如 SSH）。內部包含 `driver`, `host`, `user` 等子參數。小寫的 `link` 屬舊式寫法，未來將棄用。 |
| `WORKSPACE_ROOT`| Path | (系統自動生成) 指向當前執行指令的根目錄。 |
| `ERROR_CODE` | String | (執行時生成) 目前測試狀態。常見值與含意：<br>- `PASS`：測試成功通過。<br>- `FAIL`：測試不合格（通常為 `verify` 指令判定失敗）。<br>- `CRITICAL`：嚴重異常（腳本崩潰、語法錯誤或連線中斷）。<br>- `STOP`：操作員手動中斷測試。<br>- `CHECK`：不代表測試不通過。當希望快速掃完所有測試項目後（例如設定 `IS_FAIL_STOP=False`），系統會將最終狀態設為 `CHECK`，提示工程師需自行至 Log 或介面中判定與確認每個測試項目的實際狀況。 |
| `ERROR_DESCRIPTION`| String | (執行時生成) 失敗時的詳細描述。 |
| `RUNNER_LOGGER` | Object | (系統內部使用) 供 Python 腳本調用的 Logger 物件。 |

