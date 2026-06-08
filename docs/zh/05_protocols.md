# 03 連線層指南

Sapas 透過 `ConnectionManager` 統一管理與待測物 (DUT) 的連線。

## 驅動配置 (YAML)

在 `station.yaml` 或 `project.yaml` 中，您可以定義連線資訊：

```yaml
# Define connectivity for all physical hardware units
link:
  # --- MAIN DUT: Primary Device Under Test ---
  main_dut:
    type: ssh                # Connection type: supports ssh, adb, com
    host: 192.168.1.110      # Device IP address
    user: kumamodo           # Login username
    password: ''             # Login password
    stop_chars: ':~$'        # [Optional] Shell prompt termination characters
```

## SSH 驅動 (SSHDriver)

目前 Sapas 主要支援 SSH 連線，整合了命令執行。

### 程式碼範例：
```python
from sapas.runtime.runtime import ctx

# 獲取 SSH 連線
ssh = ctx.ssh.get('DUT1')

# 執行指令
result = ssh.exec('uname -a')
print(result.stdout)

```

## 其他協定 (規劃中)

- **ADB**: 用於 Android 裝置通訊。
- **UART (Serial)**: 用於序列埠控制。

所有驅動都封裝在 `sapas.drivers` 下，開發者可以輕鬆擴展自定義的通訊協定。
