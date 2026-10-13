# 10 機台守護者與遠端維護指南 (Station Guard & Remote Maintenance Guide)

`Sapas Station Guard` 是專為工廠產線與測試機台設計的**主動式工安防護與遠端維修互鎖系統（Industrial Safety Interlock & Remote Maintenance System）**。

在現代化智慧製造環境中，遠端研發（RD）與測試工程師經常需要透過 SSH 連線至海外或現場機台進行遠端除錯、校正或腳本測試。Station Guard 的核心目標是：
1. **防止工安危害（Physical Safety Protection）**：遠端除錯時強制在現場螢幕彈出全螢幕大紅鎖定畫面並鎖死桌面焦點，避免現場作業員或非相關人員在不知情下觸碰機構、高壓電或運動中的治具。
2. **防範測試數據污染（Shopfloor Protection）**：遠端執行腳本時強制關閉 MES/Shopfloor 數據上傳，杜絕調試數據混入正式生產數據庫。
3. **安全邊界與緊急應變（Emergency Interlock & Override）**：提供明確的主管緊急解除退場機制，並在現場強制解鎖時對遠端執行測試的行程施加「緊急煞車」，確保雙向安全。

---

## 目錄
- [1. 核心架構與防護機制](#1-核心架構與防護機制)
- [2. 常用指令一覽表](#2-常用指令一覽表)
- [3. 機台初始化部署 SOP (Commissioning)](#3-機台初始化部署-sop-commissioning)
- [4. 遠端維修日常操作流程 (Daily Operation)](#4-遠端維修日常操作流程-daily-operation)
- [5. Windows Session 0 隔離與遠端重啟機制](#5-windows-session-0-隔離與遠端重啟機制)
- [6. 現場緊急應變與主管覆寫程序 (Emergency Override)](#6-現場緊急應變與主管覆寫程序-emergency-override)
- [7. 遠端連線安全保護 (Remote Safety Policies)](#7-遠端連線安全保護-remote-safety-policies)
- [8. 常見問題與故障排除 (FAQ)](#8-常見問題與故障排除-faq)

---

## 1. 核心架構與防護機制

Station Guard 由三個層級相互協同運作：

```
+-------------------------------------------------------------+
|                      Remote Engineer                        |
|  (SSH Client / 192.168.1.113: Session 0 Background Console) |
+-------------------------------------------------------------+
                              |
       sapas guard lock       |   (SSH Execution / Auto-guard)
                              v
+-------------------------------------------------------------+
|                   Sapas State Engine (~/.sapas)             |
|       [.station_lock]  <--->  [override_event.json]         |
+-------------------------------------------------------------+
         ^                                            ^
         | Polling / Event                            | Emergency Brake
         v                                            v
+-----------------------------------+     +-------------------+
|    Station Guard Daemon (Win32)   |     | Sapas Test Engine |
|     (Session 1 Desktop Window)    |     | (Runner / TUI)    |
|   * Fullscreen Red Topmost Window |     | * Force SF=False  |
|   * Audio Alarm (winsound)        |     | * Purple UI Border|
|   * Focus Snatch & Mouse Trap     |     | * Emergency Halt  |
+-----------------------------------+     +-------------------+
```

- **守護行程 (Station Guard Daemon)**：常駐於 Windows 桌面環境（Session 1），輕量輪詢鎖定狀態，一旦偵測到鎖定即刻彈出置頂全螢幕紅畫面並播放警告音。
- **狀態引擎 (Lock Manager)**：以原子操作維護 `~/.sapas/.station_lock` 與 `override_event.json`，作為跨行程與跨網路的通訊媒介。
- **測試引擎互鎖 (Runtime Interlock)**：在執行任何測試腳本時，若感知到處於遠端 SSH 工作階段，自動強制關閉 Shopfloor，並在有鎖定需求時進行狀態互鎖。

---

## 2. 常用指令一覽表

```bash
sapas guard <subcommand> [options]
```

| 指令 | 說明 | 適用對象 |
| :--- | :--- | :--- |
| `sapas guard lock "message"` | 啟動維修鎖定，鎖定現場實體螢幕與輸入焦點 | 遠端 RD / 現場維護者 |
| `sapas guard unlock` | 解除維修鎖定，恢復現場正常作業模式 | 遠端 RD / 現場維護者 |
| `sapas guard status` | 檢視當前守護行程狀態、開機啟動與鎖定詳情 | 所有人 |
| `sapas guard install` | 將守護程式寫入 Windows Startup 資料夾並啟動 | 現場初次建機 / 遠端配置 |
| `sapas guard reinstall` | 重置所有鎖定狀態，乾淨重新安裝並重啟背景服務 | 維護排除異常 |
| `sapas guard uninstall` | 終止守護行程、清空所有狀態檔並移除開機啟動 | 系統移除 |

---

## 3. 機台初始化部署 SOP (Commissioning)

新測試機台組裝完成並配置好 Sapas 執行環境後，應執行一次性初始化安裝。

### 步驟 A：在機台本地實體電腦安裝 (推薦)
1. 登入機台 Windows 桌面，打開終端機（PowerShell 或 CMD）。
2. 切換至 Sapas 專案目錄，執行安裝指令：
   ```cmd
   sapas guard install
   ```
3. 終端機將顯示安全性公告（Security Notice）：
   - 本項目僅為使用者等級之開機啟動項目（Startup Folder），**無需 Windows 管理員 / UAC 權限**。
   - 不修改任何 Windows 登錄檔（Registry）、系統核心或硬體驅動程式。
4. 輸入 `Y` 確認安裝。
5. 守護程式將立即在背景啟動，且此後機台每次開機登入 Windows 桌面皆會自動常駐待命。

> [!TIP]
> 如果是在自動化部署腳本或 CI/CD 中執行，可加上 `-y` 參數跳過確認：
> `sapas guard install -y`

---

## 4. 遠端維修日常操作流程 (Daily Operation)

遠端工程師透過 SSH 進行現場機台維護時的標準操作流程（SOP）：

### Step 1. 連線進入機台
```bash
ssh tester@192.168.1.100
```

### Step 2. 發布維護鎖定
在動手執行任何測試或改動硬體前，先下達維護鎖定並附帶說明原因（建議用引號包覆說明文字）：
```bash
sapas guard lock "Replacing RF cable & running calibration"
```
- **成功鎖定**：終端機顯示大紅色的 `[!] [LOCKED]` 面板，現場螢幕立刻被大紅畫面完全覆蓋，顯示您的來源 IP、上鎖時間與原因。
- **防呆攔截**：若現場電腦**尚未啟動 Guard Daemon**，系統會**拒絕上鎖**並跳出具體解決指引（參見第 5 節），絕不製造「以為鎖上了」的假性安全錯覺。

### Step 3. 執行測試與調試
切換至測試資料夾，正常執行測試腳本或進入 TUI 介面：
```bash
sapas rf_test.py
# 或
sapas --tui
```
此時系統會自動確保 `ENABLE_SHOPFLOOR=False`，防止測試數據上傳至 MES。

### Step 4. 解除鎖定恢復產線
維修與測試驗證完畢後，解除維護鎖定：
```bash
sapas guard unlock
```
現場螢幕上的全螢幕大紅鎖定畫面將自動消失，桌面恢復原本狀態，產線作業員即可接手繼續生產。

---

## 5. Windows Session 0 隔離與遠端重啟機制

### 什麼是 Session 0 隔離？
Windows 作業系統為了安全性，將背景服務（包括 OpenSSH 伺服器 `sshd.exe`）隔離在 **Session 0**，而現場人員登入看到的實體桌面則處於 **Session 1 或更高**。

當您透過 SSH 連入電腦時：
- 您的終端機是跑在 Session 0（無可見圖形介面環境）。
- 若現場電腦開機後尚未啟動 Guard 服務，從 SSH 端直接拉起的 Python GUI 程式將受困於 Session 0，**現場螢幕無法看到任何視窗**。

### 遠端鎖定失敗時的雙重解決路徑

當遠端下 `sapas guard lock` 發現現場守護程式未在桌面運作時，終端機會給出兩條明確的處理路徑：

```text
Remedy Options:
  • Option 1: On-site Setup (Instant / No Reboot)
    請現場工程師在機台實體電腦上執行：
      sapas guard install
    (本地執行會立即在實體桌面生效，不需重開機)

  • Option 2: Remote Setup via SSH (Requires Station Reboot)
    1. 在目前的遠端 SSH 終端機執行安裝：
       sapas guard install
    2. 遠端發送重啟指令：
       shutdown /r /t 0
       (重開機後 Windows Explorer 自動載入 Startup 項目至 Session 1)
```

> [!IMPORTANT]
> `shutdown /r /t 0` 是 Windows 標準重啟指令（`/r` 代表 Reboot，`/t 0` 代表立即重啟無延遲）。重啟後 SSH 會暫時中斷，等待約 30~60 秒系統登入桌面後重新連線，Station Guard 就會正式常駐在實體螢幕上了。

---

## 6. 現場緊急應變與主管覆寫程序 (Emergency Override)

當現場發生緊急突發狀況（如設備卡料、冒煙，或遠端工程師失去連線導致機台被長時間鎖定），現場人員該如何處置？

### 1. 一般產線作業員 (OP) 之處置原則
- **嚴禁私自嘗試破解或強制斷電**。
- 機台畫面上清楚標註有**上鎖者 IP (Client IP)** 與**上鎖原因 (Reason)**。
- 作業員應立即通報產線領班，或在通訊群組（Teams / WeChat）中聯繫該 IP 的負責工程師。
- 遇人員安全危險時，直接拍下機台實體**緊急停止按鈕 (E-Stop)** 切斷硬體動力。

### 2. 授權主管 / 現場工程師 (PE/TE) 之緊急覆寫程序
若遠端人員失聯或確認有必要於現場強制接手，受過授權之資深工程師可透過**「安全覆寫序列（Supervisor Key Sequence）」**強制解除紅畫面：

1. 走到鎖定機台的鍵盤前。
2. 於 **10 秒內** 連續按下以下按鍵序列：
   $$\uparrow \quad \uparrow \quad \downarrow \quad \downarrow \quad \leftarrow \quad \rightarrow \quad \leftarrow \quad \rightarrow \quad \text{b} \quad \text{a} \quad \text{b} \quad \text{a}$$
   *(Up, Up, Down, Down, Left, Right, Left, Right, b, a, b, a)*
3. 全螢幕紅畫面將立即關閉，桌面控制權返還現場。

### 3. 雙向保護與緊急煞車 (Emergency Brake)
為了防止現場解鎖後，遠端工程師不知情仍在繼續送出測試指令傷害現場人員，系統建構了完整的互鎖防禦：
- 覆寫被觸發的當下，系統會寫入包含時間與事件的 `override_event.json`。
- **遠端測試腳本緊急煞車**：遠端若有腳本正在執行，下一個測試步驟會立即攔截並中止（`Exit 1`），終端機印出警示：
  ```text
  [!] [DANGER] STATION WAS FORCEFULLY UNLOCKED ON-SITE!
      Local personnel used Emergency Override Sequence.
      Aborting all testing to protect on-site personnel safety.
  ```
- **現場 TUI 重新啟動提示**：現場若有開啟 Sapas TUI，會強制彈出重啟對話框，必須重新確認狀態才能繼續。

---

## 7. 遠端連線安全保護 (Remote Safety Policies)

Sapas 在感知到遠端 SSH 工作階段時，會自動啟動以下安全策略：

1. **強制停用生產數據上傳 (`ENABLE_SHOPFLOOR=False`)**：
   - 遠端連線執行測試時，即便 YAML 設定中開啟了 `ENABLE_SHOPFLOOR: true`，系統底層的 `ExecutionContext` 也會強制覆寫為 `False`。
   - 終端機與 Log 將註記警告，確保研發調試數據絕對不會污染正式 MES 資料庫。
2. **TUI 儀表板遠端安全警示**：
   - 遠端開啟 TUI 時，全螢幕外框會自動變更為**高對比霓虹紫（Neon Purple）**，副標題顯示：
     `🌐 REMOTE (192.168.1.113) | SHOPFLOOR DISABLED`
   - 霓虹紫外框採用恆亮不閃爍設計，避免遠端網路延遲造成的畫面卡頓與視覺疲勞。
3. **自動補位上鎖 (Auto-Guard Interlock)**：
   - 遠端工程師若忘記預先執行 `sapas guard lock` 就直接執行測試腳本，系統會自動在背景替機台掛上維修鎖，避免測試漏鎖。

---

## 8. 常見問題與故障排除 (FAQ)

### Q1: 為什麼我在 SSH 執行了 `sapas guard lock`，終端機報錯說 Daemon 未運行？
**A**: 這代表現場電腦的開機啟動項目尚未安裝，或開機後未登入 Windows 桌面。請參考終端機上的說明，執行 `sapas guard install` 後使用 `shutdown /r /t 0` 重啟機台即可。

### Q2: 現場實體機台有多個螢幕（多螢幕延伸桌面），紅畫面會遮住全部嗎？
**A**: 目前 Station Guard 視窗會以 Windows 系統預設之主顯示器（Primary Display）為全螢幕置頂鎖定對象，並強行鎖定滑鼠與鍵盤焦點，使背景所有視窗皆無法接收輸入。若產線機台有特殊多螢幕配置需求，建議將測試儀器操作介面設於主顯示器。

### Q3: 執行 `sapas guard uninstall` 會清除哪些資料？
**A**: `uninstall` 是一個徹底的重置動作，會執行以下清理：
1. 終止並強制殺除所有背景中的 Guard Daemon 行程。
2. 刪除 Windows Startup 資料夾中的 `SapasStationGuard.vbs` 開機啟動腳本。
3. 清除 `~/.sapas/` 目錄下的 `.station_lock`、`override_event.json` 與 `guard.pid` 記錄檔。

### Q4: 機台重開機後，守護行程沒起來？
**A**: 
1. 檢查 Windows 帳號是否有設定「自動登入桌面（Auto-login）」。因為 Startup 資料夾是在使用者**登入桌面（Session 1）**後才會觸發。若停留在 Windows 密碼登入畫面，服務將等待登入後才會啟動。
2. 輸入 `sapas guard status` 檢查 `Startup Auto-Run` 是否顯示為 `Installed`。若否，請重新執行 `sapas guard install`。
