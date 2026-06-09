# -*- coding: utf-8 -*-
import warnings
warnings.filterwarnings(action='ignore', module='.*paramiko.*')
import re
import sys
import time
import socket
import paramiko
import codecs

from sapas.modules.log import _log, info, warn, error

# ANSI / VT100 control codes removal regex.
ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')


class SSHExecutor:
    def __init__(self, host, user, password, port=22, stop_chars=None):
        '''
        Args:
            host (str): Host ip
            user (str): username
            password (str): password for login
            port (int): SSH port (default 22)
            stop_chars (list): Default stop characters/prompts

        Returns:
            None
        '''
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self.bufsize = 65536  # Increased buffer size for better performance
        self.client = None
        self.channel = None
        self._is_closed = False
        
        # Centralized default stop_chars
        self.default_stop_chars = ["#", ":~#", "$ ", "> "]
        if stop_chars is None:
            self.stop_chars = self.default_stop_chars
        elif isinstance(stop_chars, str):
            self.stop_chars = [stop_chars]
        else:
            self.stop_chars = stop_chars

        info(f'Created new instance for {self.host} at {id(self)}', tag='SSH')

    def __get_response(self, session, timeout=3, stop_chars=None):
        """
        Poll SSH session until command completes or timeout expires.
        """
        if stop_chars is None:
            stop_chars = self.stop_chars
        elif isinstance(stop_chars, str):
            stop_chars = [stop_chars]

        output = ""
        start_time = time.time()
        
        # Use IncrementalDecoder to handle UTF-8 chars split across chunks.
        decoder = codecs.getincrementaldecoder("utf8")(errors="ignore")

        while True:
            try:
                if session.recv_ready():
                    data = session.recv(self.bufsize)
                    if not data:
                        break

                    decoded = decoder.decode(data)
                    output += decoded

                    # Performance optimization: Only check the "tail" of the output 
                    tail_check_size = 512
                    check_slice = output[-tail_check_size:]
                    cleaned_tail = ANSI_ESCAPE.sub("", check_slice)
                    
                    for stop in stop_chars:
                        if stop in cleaned_tail:
                            info(f'Polling finished - {len(output)} bytes (Prompt found)', tag='SSH')
                            return output

            except socket.timeout:
                warn(f'Socket timeout after {timeout} sec', tag='SSH')
                break
            except Exception as e:
                if 'unimplemented' in str(e):
                    continue
                else:
                    error(f'Exception {e}', tag='SSH')
                    break

            # Overall timeout.
            if (time.time() - start_time) > timeout:
                warn(f'Overall timeout {timeout} sec reached', tag='SSH')
                break

            # Connection has been closed.
            if session.exit_status_ready() and not session.recv_ready():
                break
            
            # Prevent 100% CPU usage if no data is ready.
            if not session.recv_ready():
                time.sleep(0.01)

        info(f'Polling finished - {len(output)} bytes', tag='SSH')
        return output

    def connect(self, timeout=3):
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy)
            
            # Revert to positional arguments and original timeout
            self.client.connect(self.host, 22, username=self.user, password=self.password, timeout=timeout)
            
            info(f'Successfully connected to [{self.host}]', tag='SSH')
            
            # Create interactive shell
            self.channel = self.client.invoke_shell()
            self.channel.setblocking(0)
            
            # Initial wait for prompt
            self.__get_response(self.channel, timeout=2)
            
        except Exception as e:
            error_msg = f'Failed to establish SSH connection to {self.host}: {e}'
            error(error_msg, tag='SSH')
            self.close()
            raise RuntimeError(error_msg)

    def is_active(self):
        """Check if the connection and channel are still active."""
        if not self.client or not self.channel:
            return False
        
        transport = self.client.get_transport()
        if transport is None or not transport.is_active():
            return False
            
        if self.channel.closed:
            return False
            
        return True

    def close(self):
        if self._is_closed:
            return 
        
        try:
            if self.channel:
                self.channel.close()
            if self.client:
                self.client.close()
                info(f'Connection closed [{self.host}]', tag='SSH')
        except Exception:
            pass
        finally:
            self._is_closed = True

    def send_command(self, command, timeout=3, wait_for_prompt=True, stop_chars=None):
        """
        Send a command to the SSH session.

        Args:
            command (str): The command to execute.
            timeout (int): Max seconds to wait for prompt.
            wait_for_prompt (bool): If False, return immediately after sending (async mode).
            stop_chars (list): Custom prompt characters to stop on.
        """
        max_retries = 3
        retry_delay = 1

        if not self.is_active():
            warn('Connection lost, attempting to reconnect...', tag='SSH')
            for i in range(max_retries):
                try:
                    self.connect()
                    info(f'Reconnected successfully on attempt {i+1}.', tag='SSH')
                    break
                except Exception as e:
                    if i == max_retries - 1:
                        error_msg = f"Failed to reconnect after {max_retries} attempts."
                        error(error_msg, tag='SSH')
                        raise RuntimeError(error_msg)
                    warn(f'Reconnect attempt {i+1} failed. Retrying in {retry_delay}s...', tag='SSH')
                    time.sleep(retry_delay)

        info(f'[CMD]: {command}', tag='SSH')
        cmd_to_send = command if command.endswith('\n') else command + '\n'
        
        # Double check channel after potential reconnection
        try:
            self.channel.send(cmd_to_send)
        except Exception as e:
            # Last ditch effort: if send fails even after is_active check, 
            # it might have just died. 
            warn(f'Send failed ({e}), one final retry of the command...', tag='SSH')
            self.connect()
            self.channel.send(cmd_to_send)
        
        if not wait_for_prompt:
            return f'[CMD]: {command} sent (async).'
            
        results = self.__get_response(self.channel, timeout, stop_chars)
        return results
    
    def __del__(self):
        if not self._is_closed:
            try:
                self.close()
            except:
                pass