import serial
import time
import re
from sapas.modules import log

class SerialDriver:
    def __init__(self, port, baudrate=115200, timeout=1, stop_chars=None, **kwargs):
        self.port = port
        self.baudrate = int(baudrate)
        self.timeout = timeout
        self.stop_chars = stop_chars
        self.ser = None
        self._connected = False
        self.kwargs = kwargs

    def connect(self):
        if self.ser is None or not self.ser.is_open:
            log.info(f"Connecting to {self.port} at {self.baudrate} baud", tag='SERIAL')
            try:
                self.ser = serial.Serial(
                    port=self.port,
                    baudrate=self.baudrate,
                    timeout=self.timeout,
                    write_timeout=self.timeout
                )
                self._connected = True
            except Exception as e:
                log.error(f"Failed to connect to {self.port}: {e}", tag='SERIAL')
                self._connected = False
                raise

    def exec(self, command, timeout=None, stop_chars=None, strip_echo=True, **kwargs):
        if not self._connected:
            self.connect()

        original_timeout = self.ser.timeout
        if timeout:
            self.ser.timeout = timeout

        target_stop_chars = stop_chars or self.stop_chars

        # Ensure command ends with newline
        if isinstance(command, str):
            send_cmd = command if command.endswith('\n') else command + '\n'
            cmd_log = command.strip()
        else:
            send_cmd = command
            cmd_log = command.hex()

        log.info(f"EXEC -> {cmd_log}", tag='SERIAL')

        try:
            self.ser.reset_input_buffer()
            self.ser.write(send_cmd.encode('utf-8') if isinstance(send_cmd, str) else send_cmd)
            self.ser.flush()

            response = ""
            start_time = time.time()
            last_data_time = start_time
            current_timeout = timeout or self.timeout
            
            # Inactivity timeout: if no new data for 0.5s, we consider it done (unless stop_chars is set)
            # This is different from the overall command timeout.
            inactivity_timeout = 0.5

            while True:
                now = time.time()
                
                # 1. Overall timeout check
                # If we have stop_chars, we are strict about finding it or hitting the overall timeout.
                # If we DON'T have stop_chars, we also use inactivity to decide when to stop.
                if (now - start_time) > current_timeout:
                    # If we just received data recently, give it a bit more grace time
                    if (now - last_data_time) < 0.1:
                        # Continue reading as long as data is flowing
                        pass
                    else:
                        break

                # 2. Read available data
                if self.ser.in_waiting > 0:
                    chunk = self.ser.read(self.ser.in_waiting).decode('utf-8', 'ignore')
                    response += chunk
                    last_data_time = time.time() # Update last data timestamp
                    
                    # 3. If stop_chars is defined, check if we should stop
                    if target_stop_chars:
                        if any(char in response[-5:] for char in target_stop_chars):
                            break
                    
                    time.sleep(0.01)
                else:
                    # No data in buffer
                    if target_stop_chars:
                        # If waiting for a prompt, just wait
                        time.sleep(0.01)
                    else:
                        # If no prompt, check inactivity
                        if (now - last_data_time) > inactivity_timeout:
                            break
                        time.sleep(0.05)

            # --- Post-processing ---
            response = re.sub(r'\x1b\[\?\d+[lh]', '', response)
            lines = response.splitlines()
            
            if strip_echo and lines:
                first_line = lines[0].strip()
                if first_line == cmd_log:
                    lines = lines[1:]
            
            if target_stop_chars and lines:
                last_line = lines[-1]
                if any(char in last_line for char in target_stop_chars):
                    lines = lines[:-1]

            return "\n".join(lines).strip()

        except Exception as e:
            log.error(f"Serial communication error: {e}", tag='SERIAL')
            return ""
        finally:
            self.ser.timeout = original_timeout

    def is_alive(self):
        return self.ser is not None and self.ser.is_open and self._connected

    def close(self):
        if self.ser and self.ser.is_open:
            log.info(f"Closing serial port {self.port}", tag='SERIAL')
            try:
                self.ser.close()
            except Exception:
                pass
        self.ser = None
        self._connected = False

    def __repr__(self):
        return f"<SerialDriver {self.port}@{self.baudrate}>"
