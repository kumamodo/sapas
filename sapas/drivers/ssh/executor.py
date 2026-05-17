# -*- coding: utf-8 -*-
import warnings
warnings.filterwarnings(action='ignore', module='.*paramiko.*')
import re
import sys
import time
import socket
import paramiko

from sapas.modules.log import log


class SSHExecutor:
    def __init__(self, host, user, password, stop_chars=None):
        '''
        Args:
            host (str): Host ip
            user (str): username
            password (str): password for login

        Returns:
            None

        Example:
            >>> SSHExecutor('172.168.13.1', 'root, '0000')
        '''
        self.host = host
        self.user = user
        self.password = password
        self.bufsize = 2048
        self.client = None
        self.channel = None
        self._is_closed = False
        # store default stop_chars
        if stop_chars is None:
            self.stop_chars = ["#", ":~#"]
        elif isinstance(stop_chars, str):
            self.stop_chars = [stop_chars]
        else:
            self.stop_chars = stop_chars

        log('SSH', f'Created new instance at {id(self)}')

    def __get_response(self, session, timeout=3, RealTimeOutput=False, stop_chars=None):
        """
        Poll SSH session until command completes or timeout expires.

        Args:
            session: Paramiko channel
            timeout (int|float): max seconds to wait
            RealTimeOutput (bool): if True, logs output as it arrives
            stop_chars (str or list): prompt(s) to stop on

        Returns:
            str: collected output
        """
        # Handle stop_chars.
        if stop_chars is None:
            stop_chars = ["#", ":~#"]
        elif isinstance(stop_chars, str):
            # Automatically wrap it into a list.
            stop_chars = [stop_chars]

        # Remove ANSI / VT100 control codes.
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

        output = ""
        start_time = time.time()
        # non-blocking
        session.setblocking(0)

        while True:
            # Prevent 100% CPU usage.
            time.sleep(0.05)
            try:
                if session.recv_ready():
                    data = session.recv(self.bufsize)
                    if not data:
                        continue

                    decoded = data.decode("utf8", "ignore")
                    output += decoded

                    if RealTimeOutput:
                        log('SSH', decoded, end='')

                    # Compare stop_chars after stripping control codes.
                    cleaned_output = ansi_escape.sub("", output)
                    for stop in stop_chars:
                        if stop in cleaned_output:
                            # Return immediately when a stop_char is found.
                            log('SSH', f'Polling finished - {len(output)} bytes')
                            return output

            except socket.timeout:
                log('SSH', f'Socket timeout after {timeout} sec')
                break
            except Exception as e:
                if 'unimplemented' in str(e):
                    continue
                else:
                    log('SSH', f'Exception {e}')
                    break

            # Overall timeout.
            if (time.time() - start_time) > timeout:
                log('SSH', f'Overall timeout {timeout} sec')
                break

            # Connection has been closed.
            if session.exit_status_ready():
                break

        log('SSH', f'Polling finished - {len(output)} bytes')
        return output

    def connect(self):
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy)
            self.client.connect(self.host, 22, username=self.user, password=self.password, timeout=3)
            log('SSH', 'Successfully connected to [{}]'.format(self.host))
            self.channel = self.client.invoke_shell()
        except Exception as e:
            log('SSH', 'Can not establish a connection: {}'.format(e))
            self.client.close()
            sys.exit(0)

    def close(self):
        if self._is_closed:
            return 
        
        try:
            if self.channel:
                self.channel.close()
            if self.client:
                self.client.close()
                log('SSH', f'Connection closed [{self.host}]')
            self._is_closed = True
        except Exception:
            pass

    def send_command(self, command, timeout=3, ignoreResponse=False, RealTimeOutput=False, stop_chars=None):
        # RTO mean: Real-Time-Output
        log('SSH', f'[CMD]: {command}')
        self.channel.send(command + '\n')
        if ignoreResponse:
            return f'[CMD]: {command} Done.'
        results = self.__get_response(self.channel, timeout, RealTimeOutput, stop_chars)
        return results
    
    def __del__(self):
        # Destructor acts only as a last line of defense.
        # Note: During Python shutdown, global variables may already be None.
        # Check if sys still exists; if not, Python is shutting down.
        if sys is not None and not self._is_closed:
            self.close()