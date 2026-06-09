import logging

from sapas.drivers.ssh.executor import SSHExecutor
from sapas.drivers.ssh.sftp import SFTPClient
from sapas.modules.log import _log, info, error

# Disable printing of Paramiko “unimplemented message” logs.
logging.getLogger("paramiko").setLevel(logging.ERROR)


class SSHDriver:

    def __init__(self, host, user, password, stop_chars=None):
        self.host = host
        self.user = user
        self.password = password
        self.stop_chars = stop_chars

        self._ssh = SSHExecutor(host, user, password, stop_chars=stop_chars)
        # Lazy initialization of SFTP connection (initialized only when needed).
        self._sftp = None
        self._connected = False
        self._sftp_connected = False

    def connect(self):
        if self.is_alive():
            return  # already connected

        info(f"Connecting to [{self.host}]", tag='SSH')
        try:
            self._ssh.connect()
            self._connected = True
        except Exception as e:
            self._connected = False
            error(f"Failed to connect to {self.host}: {e}", tag='SSH')
            raise

    def exec(self, command, timeout=3, wait_for_prompt=True, stop_chars=None, **kwargs):
        if stop_chars is None:
            stop_chars = self.stop_chars

        return self._ssh.send_command(
            command,
            timeout=timeout,
            wait_for_prompt=wait_for_prompt,
            stop_chars=stop_chars,
        )

    def is_alive(self):
        """Check if the SSH connection is active."""
        if self._ssh:
            return self._ssh.is_active()
        return False

    def reconnect(self):
        info(f"Reconnecting to {self.host}", tag='SSH')
        self.close()
        self.connect()

    def ensure_connected(self):
        if not self._connected or not self.is_alive():
            self.connect()

    def __repr__(self):
        return f"<SSHDriver {self.host}>"

    # SFTP functionality (lazy initialization).
    def connect_sftp(self):
        if self._sftp is None:
            self._sftp = SFTPClient(self.host, self.user, self.password)
        if not self._sftp_connected:
            self._sftp.connect()
            self._sftp_connected = True

    def upload(self, local_path, remote_path):
        self.connect_sftp()
        info(f"[UPLOAD]: {local_path} -> {remote_path}", tag='SSH')
        return self._sftp.putFile(local_path, remote_path)

    def download(self, remote_path, local_path):
        self.connect_sftp()
        info(f"[DOWNLOAD]: {remote_path} -> {local_path}", tag='SSH')
        return self._sftp.getFile(remote_path, local_path)

    def upload_dir(self, local_dir, remote_dir):
        self.connect_sftp()
        info(f"[UPLOAD_DIR]: {local_dir} -> {remote_dir}", tag='SSH')
        return self._sftp.putFolder(local_dir, remote_dir)

    def download_dir(self, remote_dir, local_dir):
        self.connect_sftp()
        info(f"[DOWNLOAD_DIR]: {remote_dir} -> {local_dir}", tag='SSH')
        return self._sftp.getFolder(remote_dir, local_dir)

    def close(self):
        if not self._connected:
            return 
       
        # Call the close method of the Executor above.
        if self._ssh:
            self._ssh.close()
        
        if self._sftp and self._sftp_connected:
            self._sftp.close()
            
        self._connected = False
        self._sftp_connected = False

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass