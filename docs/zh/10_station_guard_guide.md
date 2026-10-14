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
- [3. 現場機台 OpenSSH 啟用與連線保活指南 (Station OpenSSH Setup)](#3-現場機台-openssh-啟用與連線保活指南-station-openssh-setup)
- [4. 機台初始化部署 SOP (Commissioning)](#4-機台初始化部署-sop-commissioning)
- [5. 遠端維修日常操作流程 (Daily Operation)](#5-遠端維修日常操作流程-daily-operation)
- [6. Windows Session 0 隔離與遠端重啟機制](#6-windows-session-0-隔離與遠端重啟機制)
- [7. 現場緊急應變與主管覆寫程序 (Emergency Override)](#7-現場緊急應變與主管覆寫程序-emergency-override)
- [8. 遠端連線安全保護 (Remote Safety Policies)](#8-遠端連線安全保護-remote-safety-policies)
- [9. 常見問題與故障排除 (FAQ)](#9-常見問題與故障排除-faq)

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

## 3. 現場機台 OpenSSH 啟用與連線保活指南 (Station OpenSSH Setup)

在 Windows 產線電腦上，要達成穩定且安全的遠端連線，推薦採用**「SSH Key 免密碼金鑰登入」**。此方式能徹底避開 Windows Hello PIN 碼、微軟線上帳號（MS Account）密碼無法登入，以及自動化測試需頻繁打密碼的困境。

### 3.1 現場被連線端 (Station Server) 快速配置

> [!IMPORTANT]
> 現場機台以下步驟請在 Windows 中以**「系統管理員身分 (Run as Administrator)」**開啟 PowerShell 執行。

#### Step 1. 安裝 OpenSSH Server 選用功能
```powershell
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
```

#### Step 2. 啟動服務並設定開機自啟
```powershell
Start-Service sshd
Set-Service -Name sshd -StartupType 'Automatic'
```

#### Step 3. 防火牆規則全開 (放行公用與私人網路)
Windows 預設防火牆規則通常只放行「私人網路」。若機台網卡被判定為「公用網路（Public）」，遠端會連不進去。執行以下指令放行所有 Profile：
```powershell
Set-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -Profile Any
```

#### Step 4. 【實戰關鍵】解除管理員公鑰綁架與開啟連線保活
微軟預設規定：若登入者具備 Administrator 管理員權限，OpenSSH 會強制忽略使用者家目錄的 `authorized_keys`。同時，預設未開啟主動心跳（KeepAlive），閒置數分鐘即會被交換機中斷連線。

以管理員身分開啟設定檔：
```powershell
notepad C:\ProgramData\ssh\sshd_config
```

進行以下兩處核心修改：

1. **開啟 Server 端心跳保活（防止閒置斷線）**：
   找到 `ClientAliveInterval` 與 `ClientAliveCountMax`（約第 66 行），去掉前面 `#` 註解並設定數值：
   ```text
   ClientAliveInterval 30
   ClientAliveCountMax 5
   ```
   *(現場主機會每 30 秒主動發送心跳檢查連線，連續 5 次未回應才斷開，徹底防止 NAT 路由器與防火牆踢除連線)*

2. **解除管理員專用公鑰限制（回歸標準 `~/.ssh/authorized_keys`）**：
   滑到檔案最底部（約第 87~88 行），將這兩行前面**加上 `#` 註解掉**：
   ```text
   #Match Group administrators
   #       AuthorizedKeysFile __PROGRAMDATA__/ssh/administrators_authorized_keys
   ```

存檔並關閉 Notepad。

#### Step 5. （可選推薦）將預設 Shell 改為 PowerShell
Windows 預設連進去是傳統的 CMD，若習慣 PowerShell 的語法與模組，可執行：
```powershell
New-ItemProperty -Path "HKLM:\SOFTWARE\OpenSSH" -Name DefaultShell -Value "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" -PropertyType String -Force
```

#### Step 6. 重啟 SSH 服務套用設定
```powershell
Restart-Service sshd
```

---

### 3.2 設定 SSH 公鑰免密碼登入 (Key Pairing)

#### 步驟 A：在連線端電腦（Client / 工程師筆電）
1. 產生 SSH Key（若本機已有則可跳過）：
   ```bash
   ssh-keygen -t ed25519
   ```
2. 檢視並複製您的 Public Key 內容：
   - **Windows Client**: `type ~/.ssh/id_ed25519.pub`
   - **macOS / Linux Client**: `cat ~/.ssh/id_ed25519.pub`
   *(複製整串開頭為 `ssh-ed25519 AAAA...` 的文字)*

#### 步驟 B：在現場機台電腦（Server / 被連線端）
1. 進入登入使用者的目錄 `C:\Users\<使用者名稱>\.ssh\`（若無此資料夾請手動新增）。
2. 在該資料夾內建立或編輯 `authorized_keys` 檔案（**注意：檔案無任何副檔名**）。
3. 將步驟 A 複製的公鑰文字貼入並存檔。
4. **【權限修復】執行權限重置（極重要，避免因權限過大被 SSH 拒絕）**：
   在現場電腦以管理員身分執行以下兩行 PowerShell 指令：
   ```powershell
   icacls "$env:USERPROFILE\.ssh" /inheritance:r /grant "$($env:USERNAME):F" /grant "SYSTEM:F"
   icacls "$env:USERPROFILE\.ssh\authorized_keys" /inheritance:r /grant "$($env:USERNAME):F" /grant "SYSTEM:F"
   ```

---

### 3.3 連線測試與驗證

1. **查詢機台連線資訊**（在現場機台終端機執行）：
   - 查詢 IP：執行 `ipconfig`（查看 IPv4 位址，如 `192.168.1.50`）。
   - 查詢帳號：執行 `whoami`（例如顯示 `DESKTOP-88NEIUV\tester`，使用者名稱即為 `tester`）。
2. **在工程師筆電（Client 端）發起連線**：
   ```bash
   ssh tester@192.168.1.50
   ```
   🎉 **無需輸入密碼，1 秒內直接進入現場機台終端機！**

---

### 3.4 遠端長連線防斷線指南 (KeepAlive & 電源最佳實踐)

在產線調試時，最常遇到連線放著幾分鐘沒動就跳出 `Connection reset by peer` 或 `Broken pipe`，這通常是兩大原因造成：

1. **路由器 / 交換器的 NAT 閒置超時 (Idle Timeout)**：
   - 除了前面在機台端設定的 `ClientAliveInterval 30` 外，建議工程師在自己的筆電（Client 端）的 `~/.ssh/config` 加上全域心跳設定：
     ```text
     Host *
         ServerAliveInterval 60
         ServerAliveCountMax 3
     ```
2. **現場機台電腦的自動睡眠 (Power Management)**：
   - 現場 Windows 預設閒置 10~15 分鐘會自動進入「睡眠（Sleep）」，導致網卡休眠中斷 SSH。
   - **處置**：至現場電腦的 **[設定] $\rightarrow$ [系統] $\rightarrow$ [電源與睡眠]**，將「接通電源時，讓電腦進入睡眠狀態」修改為 **「永不 (Never)」**。

---

## 4. 機台初始化部署 SOP (Commissioning)

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

## 5. 遠端維修日常操作流程 (Daily Operation)

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
- **防呆攔截**：若現場電腦**尚未啟動 Guard Daemon**，系統會**拒絕上鎖**並跳出具體解決指引（參見第 6 節），絕不製造「以為鎖上了」的假性安全錯覺。

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

## 6. Windows Session 0 隔離與遠端重啟機制

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

## 7. 現場緊急應變與主管覆寫程序 (Emergency Override)

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

## 8. 遠端連線安全保護 (Remote Safety Policies)

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

## 9. 常見問題與故障排除 (FAQ)

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
