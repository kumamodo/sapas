# 03 連線層指南

Sapas 透過 `ConnectionManager` 統一管理與待測物 (DUT) 的連線。

## 驅動配置 (YAML)

在 `station.yaml` 或 `project.yaml` 中，您可以定義連線資訊：

```yaml
link:
  DUT1:
    driver: ssh
    host: 192.168.1.100
    user: root
    password: password
```

## SSH 驅動 (SSHDriver)

目前 Sapas 主要支援 SSH 連線，整合了命令執行與 SFTP 檔案傳輸。

### 程式碼範例：
```python
from sapas.runtime.runtime import ctx

# 獲取 SSH 連線
ssh = ctx.ssh.get('DUT1')

# 執行指令
result = ssh.exec('uname -a')
print(result.stdout)

# 上傳檔案
ssh.upload('local_file.txt', '/tmp/remote_file.txt')
```

## 其他協定 (規劃中)

- **ADB**: 用於 Android 裝置通訊。
- **UART (Serial)**: 用於序列埠控制。

所有驅動都封裝在 `sapas.drivers` 下，開發者可以輕鬆擴展自定義的通訊協定。
