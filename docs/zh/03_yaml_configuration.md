# 03 配置規範 (YAML Configuration)

Sapas 採用多層級的 YAML 配置系統，讓開發者能彈性管理全域環境、專案變數與工位設定。

## 1. 配置層級與優先權

當系統啟動時，會按以下順序載入並遞迴合併（Deep Merge）設定檔。**後者會覆蓋前者的同名變數**：

1.  **`configs/project.yaml`** (專案層級預設值 - 最低)
2.  **`stations/{STATION}/station.yaml`** (工位層級標配 - 進 Git)
3.  **`site_infra.yaml`** (本機機台環境設定 - 不進 Git，最高優先覆蓋)

**優先權關係**：
`site_infra.yaml` (本地最高覆蓋) > `stations/{STATION}/station.yaml` (工位標配) > `configs/project.yaml` (專案預設)

**設計哲學**：
*   **`station.yaml`** 屬於專案版控（進 Git），用來定義工位的**標準出廠規格**（例如 SMT 站標配固緯、FA 站標配 ITECH）。
*   **`site_infra.yaml`** 屬於實體機台本地配置（不上 Git），用來管理現場 IT 環境（Shopfloor IP）以及**個別機台硬體的本地覆蓋**（例如該實體機台 COM Port 差異、或 RD 本地開發除錯設定）。
*   **RD 開發零污染**：RD 在本機座位開發時，若手邊接線不同，只需在本地 `site_infra.yaml` 覆蓋 `LINK` 設定，Git 始終保持純淨，不會影響產線代碼。

---

## 2. 變數存取介面：sapas.var

在 Sapas 框架中，所有合併後的設定以及執行期間動態產生的數據，都被視為「全域變數」。不論是在 **Python 腳本 (Script)** 還是 **測試流程 (Flow)** 中，都可以透過 `sapas.var` 進行存取或寫入。

### 存取與寫入方式：
*   **讀取變數**：使用 `sapas.var.get("KEY_NAME")`。
*   **寫入/更新變數**：使用 `sapas.var.set("KEY_NAME", value)`。

這使得 `sapas.var` 成為一個強大的全域數據中樞，方便在不同的測試步驟之間傳遞資訊（例如：在步驟 A 存入量測值，在步驟 B 根據該值進行判斷）。

---

## 3. 各設定檔存在的意義

### site_infra.yaml (本機機台與現場環境)
*   **位置**：通常放在工作區根目錄（如 `example/site_infra.yaml`，建議加入 `.gitignore`）。
*   **用途**：現場環境專屬設定與本地機台硬體覆蓋。包含 MES/Shopfloor 伺服器、全廠設定，以及當前電腦要跑的 `PROJECT_NAME` 與 `STATION_NAME`。
*   **典型參數**：`PROJECT_NAME`, `STATION_NAME`, `FACTORY_LOCATION`, `ENABLE_SHOPFLOOR`, `SMB_SERVER_IP`, `LINK`（本機硬體連線覆蓋）。

### project.yaml (專案定義)
*   **位置**：`{Project}/configs/project.yaml`。
*   **用途**：定義該專案的所有工位都會用到的邏輯與連線基礎。例如：DUT 通用連線、韌體預期版本、共用的超時時間。
*   **典型參數**：`EXPECTED_FW_VER`, `TIMEOUT_RETRY`, `LINK`。

### station.yaml (工位標配)
*   **位置**：`{Project}/stations/{StationName}/station.yaml`。
*   **用途**：定義該工位的標準出廠標配硬體與測試規格（進 Git）。
*   **典型參數**：`LINK` (工位專屬儀器如電源供應器、治具 PLC), `STATION_ID`。

---

## 3. 系統核心保留變數

以下是 Sapas 框架內部會引用或自動生成的關鍵參數。請避免將其用於不相關的用途。

| 參數名稱 | 類型 | 說明 |
| :--- | :--- | :--- |
| `PROJECT_NAME` | String | 專案名稱。系統據此尋找對應的資料夾。 |
| `STATION_NAME` | String | 工位名稱。系統據此尋找 `station.yaml` 與預設 `.flow`。 |
| `TEST_FLOW` | String | 鎖定目前工位應執行的流程檔（格式：`流程檔名.flow`）。僅在 `site_infra.yaml` 內生效以達防呆目的。 |
| `IS_FAIL_STOP` | Boolean | 若為 `True`，當 `verify` 指令失敗時，會立即中斷測試並跳轉至 `on_fail`。 |
| `STATION_TIMEOUT` | Number | 工位總執行超時時間（秒）。預設 `0` 表示不限制。若總耗時超過此門檻，測試將自動中斷並標記為 `STATION_TIMEOUT` 失敗。 |
| `IS_EXCEPTION_STOP` | Boolean | 若為 `True`，當腳本拋出異常或崩潰（非 `80` 錯誤碼）時，會立即中斷測試。設為 `False` 可在開發時搭配 `IS_FAIL_STOP` 做完整測試。 |
| `ENABLE_SHOPFLOOR`| Boolean | 表示當前測試是否連接 Shopfloor。 |
| `ENABLE_SMB` | Boolean | 是否將測試過程中的 Log 與數據 (通常為 `output/{序號}`) 上傳至 Server 以供日後追蹤。 |
| `LINK` | Dict | 定義連線驅動（如 SSH、ADB、UDP、UART）。內部包含 `type`, `host`, `user`, `password`, `source_ip` (可選，綁定 PC 本地網卡來源 IP), `drain_timeout` (可選，UDP 封包排空超時) 等子參數。小寫的 `link` 屬舊式寫法，未來將棄用。 |
| `WORKSPACE_ROOT`| Path | (系統自動生成) 指向當前執行指令的根目錄。 |
| `ERROR_CODE` | String | (執行時生成) 目前測試狀態。常見值與含意：<br>- `PASS`：測試成功通過。<br>- `FAIL`：測試不合格（通常為 `verify` 指令判定失敗）。<br>- `CRITICAL`：嚴重異常（腳本崩潰、語法錯誤或連線中斷）。<br>- `STOP`：操作員手動中斷測試。<br>- `CHECK`：不代表測試不通過。當希望快速掃完所有測試項目後（例如設定 `IS_FAIL_STOP=False`），系統會將最終狀態設為 `CHECK`，提示工程師需自行至 Log 或介面中判定與確認每個測試項目的實際狀況。 |
| `ERROR_DESCRIPTION`| String | (執行時生成) 失敗時的詳細描述。 |
| `RUNNER_LOGGER` | Object | (系統內部使用) 供 Python 腳本調用的 Logger 物件。 |

