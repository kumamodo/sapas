# 01 快速開始 (Quick Start)

本指南將協助您快速搭建 Sapas 開發環境，並使用內建的 `Alishan` 範例專案執行第一個測試流程。

## 環境需求

- Python 3.8 或更高版本
- pip (Python 套件管理工具)

## 安裝步驟

1. 進入專案目錄：

   ```bash
   cd sapas
   ```
2. 以開發模式安裝依賴：

   ```bash
   pip install -e .
   ```

## 專案結構範例 (Alishan)

Sapas 的 `example` 目錄中包含了一個完整的專案 `Alishan`。其結構如下：

```
sapas/
├── site_infra.yaml          # 全域環境設定
└── example/                 # 範例工作區
    ├── site_infra.yaml      # (推薦) 在工作區放置設定檔
    └── Alishan/             # 阿里山專案 (專案名稱)
        ├── configs/         # 專案級別變數
        ├── criteria/        # 測試規範 (CSV 格式)
        ├── flows/           # 測試流程定義
        ├── scripts/         # Python 測試腳本
        └── stations/        # 工位專屬設定 (Function, Wireless)
```

## 執行範例測試

為了操作簡便，建議先切換到工作目錄（如 `example`）：

```bash
cd example

# 啟動 Alishan 專案的 Function 工位
sapas --project Alishan --station Function
```

### 自動化執行 (懶人包)

如果您在 `site_infra.yaml` 中已經指定好常用的專案與工位：

```yaml
# site_infra.yaml 內容範例
PROJECT_NAME: Alishan
STATION_NAME: Function
```

那麼您只需要輸入以下指令即可啟動：

```bash
# 直接啟動 (CLI 模式)
sapas

# 或是直接啟動 TUI 圖形介面
sapas --tui
```

### 常用參數

- `--project`: 指定專案目錄名稱。
- `--station`: 指定工位名稱 (對應 `stations/` 下的資料夾)。
- `--test_flow`: 強制指定特定的 `.flow` 檔案。
- `--tui`: 啟動圖形化終端介面 (Dashboard)。
