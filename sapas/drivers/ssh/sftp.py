import os
import pathlib
from pathlib import Path
import paramiko
from stat import S_ISDIR

from sapas.modules.log import _log, info, error

class SFTPClient:
    def __init__(self, host, user, password, port=22):
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self.transport = None
        self.sftp = None
        self.put_folder_count = []

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def connect(self):
        try:
            self.transport = paramiko.Transport((self.host, self.port))
            self.transport.connect(username=self.user, password=self.password)
            self.sftp = paramiko.SFTPClient.from_transport(self.transport)
            info(f"Successfully connected to [{self.host}:{self.port}]", tag='SFTP')
        except Exception as e:
            error(f'Can not establish a connection: {e}', tag='SFTP')
            if self.transport:
                try:
                    self.transport.close()
                except Exception:
                    pass
                self.transport = None
            raise
    
    def make_dirs(self, remote_directory):
        try:
            remote_directory = remote_directory.replace('\\', '/')
            dirs = [d for d in remote_directory.split('/') if d]
            path = ''
            for dir in dirs:
                path += '/' + dir
                try:
                    self.sftp.stat(path)
                except IOError:
                    try:
                        self.sftp.mkdir(path)
                    except IOError:
                        pass
        except Exception as e:
            error(f"Failed for creating the remote directory: {str(e)}", tag='SFTP')
            raise

    def put_file(self, src_file, dst_file):
        '''
        @src_file: source file path(include file name)
        @dst_file: destination file path(include file name)
        '''
        info(f'[UPLOAD]: {src_file} --> {dst_file}', tag='SFTP')
        remote_dir = os.path.dirname(dst_file.replace('\\', '/'))
        if remote_dir:
            self.make_dirs(remote_dir)
        self.sftp.put(src_file, dst_file)

    def get_file(self, remote_file, local_file):
        '''
        @remote_file: source file path(include file name)
        @local_file: destination file path(include file name)
        '''
        info(f'[DOWNLOAD]: {remote_file} --> {local_file}', tag='SFTP')
        local_dir = os.path.dirname(local_file)
        if local_dir:
            os.makedirs(local_dir, exist_ok=True)
        self.sftp.get(remote_file, local_file)

    def __put_folder_execute(self, local_dir, remote_dir):
        if remote_dir.endswith('/'):
            remote_dir = remote_dir[:-1]

        for file in os.listdir(local_dir):
            local_path = os.path.join(local_dir, file)
            remote_path = f"{remote_dir}/{file}"
            if os.path.isfile(local_path):
                info(f'[UPLOAD]: {local_path} -> {remote_path}', tag='SFTP')
                self.sftp.put(local_path, remote_path)
                self.put_folder_count.append(file)
            else:
                self.make_dirs(remote_path)
                info(f'[MKDIR]: {remote_path}', tag='SFTP')
                self.__put_folder_execute(local_path, remote_path)
        return len(self.put_folder_count)
    
    def put_folder(self, local_dir, remote_dir):
        self.put_folder_count.clear()
        folder_name = os.path.basename(local_dir.rstrip('/\\'))
        remote_dir = remote_dir.replace('\\', '/').rstrip('/')
        
        # 若 remote_dir 的最後一層名稱不等於 local_dir 名稱，才自動補上資料夾名稱
        if os.path.basename(remote_dir) != folder_name:
            remote_dir = f"{remote_dir}/{folder_name}"

        self.make_dirs(remote_dir)
        return self.__put_folder_execute(local_dir, remote_dir)
    
    def get_folder(self, remote_dir, local_dir):
        '''
        @remote_dir: source folder path(include folder name)
        @local_dir: destination folder path(include folder name)
        '''
        if not os.path.exists(local_dir):
            os.makedirs(local_dir)

        all_files = self._get_all_files_in_remote_dir(remote_dir)
        # copy remote file to local folder
        for full_file_name in all_files:
            remote_file_path, filename = os.path.split(str(full_file_name))
            local_path = os.path.join(local_dir, os.path.relpath(remote_file_path, remote_dir))
            Path(local_path).mkdir(parents=True, exist_ok=True)
            local_filename = os.path.join(local_path, filename)
            info(f'[DOWNLOAD]: {full_file_name} -> {local_filename}', tag='SFTP')
            self.sftp.get(full_file_name, local_filename)
        
        return len(all_files)

    def _get_all_files_in_remote_dir(self, remote_dir):
        all_files = list()
        remote_dir = remote_dir.replace('\\', '/').rstrip('/')

        remote_files = self.sftp.listdir_attr(remote_dir)
        for remote_file in remote_files:
            filename = remote_dir + '/' + remote_file.filename
            if S_ISDIR(remote_file.st_mode):
                all_files.extend(
                    self._get_all_files_in_remote_dir(filename))
            else:
                all_files.append(filename)
        return all_files

    def mkdir(self, path, mode=511, ignore_existing=False):
        # Augments mkdir by adding an option to not fail if the folder exists
        if ignore_existing:
            self.make_dirs(path)
        else:
            self.sftp.mkdir(path, mode)

    def check_file_exists(self, file_path):
        try:
            attrs = self.sftp.stat(file_path.replace('\\', '/'))
            info(f"File exists: {os.path.basename(file_path)} ({attrs.st_size} bytes)", tag='SFTP')
            return True
        except IOError:
            return False

    def close(self):
        if self.sftp is not None:
            try:
                self.sftp.close()
            except Exception:
                pass
            self.sftp = None
        if self.transport is not None:
            try:
                self.transport.close()
            except Exception:
                pass
            self.transport = None
        info('Connection closed', tag='SFTP')

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass