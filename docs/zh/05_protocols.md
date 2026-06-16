# 05 連線層指南

Sapas 透過 `ConnectionManager` 統一管理與待測物 (DUT) 的連線。

## 驅動配置 (YAML)

在 `station.yaml` 或 `project.yaml` 中，您可以定義連線資訊：

```yaml
# Define connectivity for all physical hardware units
link:
  # --- MAIN DUT: Primary Device Under Test ---
  main_dut:
    type: ssh                # Connection type: supports ssh, adb, uart
    host: 192.168.1.110      # Device IP address
    user: kumamodo           # Login username
    password: ''             # Login password
    stop_chars: ':~$'        # [Optional] Shell prompt termination characters
```

## 存取驅動程式 (Python API)

Sapas 在腳本中提供了兩種獲取連線實例的方式：

1.  **通用連線管理器 (Universal)**：使用 `sapas.link.get(name)`，適用於所有通訊協定。
2.  **專用上下文管理器 (Dedicated)**：使用 `ctx.ssh.get(name)`、`ctx.adb.get(name)`、`ctx.udp.get(name)` 或 `ctx.uart.get(name)`，可提供更好的開發者提示與協定驗證。

---

## SSH 驅動 (SSHDriver)

整合了 SSH 遠端命令執行。

### 程式碼範例：
```python
import sapas
from sapas.runtime.runtime import ctx

# 方法 A：通用存取方式
ssh = sapas.link.get('main_dut')

# 方法 B：專用存取方式
ssh = ctx.ssh.get('main_dut')

# 執行指令
result = ssh.exec('uname -a')
print(result)
```

## ADB 驅動 (ADBDriver)

支援 Android 裝置，具備「智慧雙模」 (USB 優先並自動備援網路) 與「自動偵測」功能。

### 程式碼範例：
```python
import sapas
from sapas.runtime.runtime import ctx

# 方法 A：通用存取方式
device = sapas.link.get('adb_device')

# 方法 B：專用存取方式
device = ctx.adb.get('adb_device')

# 執行 shell 指令
model = device.exec('getprop ro.product.model')
print(model)
```


## UDP 驅動 (UDPDriver)

用於透過 UDP 封包與 MCU 或其他網路硬體進行通訊。

### 配置範例：
```yaml
link:
  mcu:
    type: udp
    host: "192.168.1.111"
    server_port: 5088
    client_port: 5088
```

### 程式碼範例：
```python
from sapas.runtime.runtime import ctx

# 獲取 UDP 連線
udp = ctx.udp.get('mcu')

# 發送指令並獲取回傳
response = udp.exec('READ_VER')
print(response)
```

## UART 驅動 (SerialDriver)

用於透過序列埠 (RS232/TTL) 與硬體進行通訊。

### 配置範例：
```yaml
link:
  uart_device:
    type: uart
    port: "COM4"             # 序列埠名稱 (例如 Win: COM3, Linux: /dev/ttyUSB0)
    baudrate: 115200         # [選填] 預設：115200
    timeout: 1               # [選填] 預設：1 (秒)
    stop_chars: ":~$"        # [選填] 等待停止的提示字元
```

### 程式碼範例：
```python
import sapas
from sapas.runtime.runtime import ctx

# 方法 A：通用存取方式
uart = sapas.link.get('uart_device')

# 方法 B：專用存取方式
uart = ctx.uart.get('uart_device')

# 執行指令並獲取乾淨的輸出 (已自動去 Echo)
response = uart.exec('uname -a')
print(response)
```

所有驅動都封裝在 `sapas.drivers` 下，開發者可以輕鬆擴展自定義的通訊協定。
