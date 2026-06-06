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

    def connect(self):
        try:
            self.transport = paramiko.Transport((self.host, self.port))
            self.transport.connect(username=self.user, password=self.password)
            self.sftp = paramiko.SFTPClient.from_transport(self.transport)
            info(f"Successfully connected to [{self.host}:{self.port}]", tag='SFTP')
        except Exception as e:
            error(f'Can not establish a connection: {e}', tag='SFTP')
            raise

            if hasattr(self, 'transport'):
                self.transport.close()
    
    def makeDirs(self, remote_directory):
        try:
            dirs = remote_directory.strip('/').split('/')
            path = ''
            for dir in dirs:
                path += '/' + dir
                try:
                    self.sftp.stat(path)
                except IOError:
                    self.sftp.mkdir(path)
        except Exception as e:
            error(f"Failed for creating the remote directiry.{str(e)}", tag='SFTP')
            raise

    def putFile(self, srcFile, dstFile):
        '''
        @srcFile: source file path(include file name)
        @dstFile: destination file path(include file name)
        '''
        info(f'[UPLOAD]: {srcFile} --> {dstFile}', tag='SFTP')
        self.sftp.put(srcFile, dstFile)

    def getFile(self, remotefile, localfile):
        '''
        @remotefile: source file path(include file name)
        @localfile: destination file path(include file name)
        '''
        info(f'[DOWNLOAD]: {remotefile} --> {localfile}', tag='SFTP')
        self.sftp.get(remotefile, localfile)

    def __putFolder_execute(self, local_dir, remote_dir):
        if remote_dir[-1] == '/':
            remote_dir = remote_dir[0:-1]

        for file in os.listdir(local_dir):
            if os.path.isfile(os.path.join(local_dir, file)):
                info(f'[UPLOAD]: {os.path.join(local_dir, file)} -> {"%s/%s" % (remote_dir, file)}', tag='SFTP')
                self.sftp.put(os.path.join(local_dir, file), '%s/%s' % (remote_dir, file))
                self.putFolderCount.append(file)
            else:
                self.mkdir('%s/%s' % (remote_dir, file), ignore_existing=True)
                info(f'[MKDIR]: {"%s/%s" % (remote_dir, file)}', tag='SFTP')
                self.__putFolder_execute(os.path.join(local_dir, file), '%s/%s' % (remote_dir, file))
        return len(self.putFolderCount)
    
    def putFolder(self, local_dir,remote_dir):
        self.putFolderCount.clear()
        remote_dir = os.path.join(remote_dir, os.path.basename(local_dir))
        remote_dir = pathlib.PureWindowsPath(remote_dir).as_posix()
        try:
            self.sftp.mkdir(remote_dir)
        except OSError:
            pass
        return self.__putFolder_execute(local_dir, remote_dir)
    
    def getFolder(self, remote_dir, local_dir):
        '''
        @remote_dir: source folder path(include folder name)
        @local_dir: destination folder path(include folder name)
        '''
        if not os.path.exists(local_dir):
            os.makedirs(local_dir)

        all_files = self._get_all_files_in_remote_dir(remote_dir)
        # copy remote file to local folder
        for fullfilename in all_files:
            remoteFilePath, filename = os.path.split(str(fullfilename))
            local_path = os.path.join(local_dir, os.path.relpath(remoteFilePath, remote_dir))
            Path(local_path).mkdir(parents=True, exist_ok=True)
            local_filename = os.path.join(local_path, filename)
            info(f'[DOWNLOAD]: {fullfilename} -> {local_filename}', tag='SFTP')
            self.sftp.get(fullfilename, local_filename)
        
        return len(all_files)

    def _get_all_files_in_remote_dir(self, remote_dir):
        all_files = list()
        if remote_dir[-1] == '/':
            remote_dir = remote_dir[0:-1]

        remoteFiles = self.sftp.listdir_attr(remote_dir)
        for remoteFile in remoteFiles:
            filename = remote_dir + '/' + remoteFile.filename
            if S_ISDIR(remoteFile.st_mode):
                all_files.extend(
                    self._get_all_files_in_remote_dir(filename))
            else:
                all_files.append(filename)
        return all_files

    def mkdir(self, path, mode=511, ignore_existing=False):
        #Augments mkdir by adding an option to not fail if the folder exists
        try:
            self.sftp.mkdir(path, mode)
        except IOError:
            if ignore_existing:
                pass
            else:
                raise

    def checkFileExists(self, filePath):
        try:
            attrs = self.sftp.stat(filePath)
            info(f"File exists: {os.path.basename(filePath)} ({attrs.st_size} bytes)", tag='SFTP')
            return True
        except IOError:
            return False

    def close(self):
        if hasattr(self, 'sftp'):
            self.sftp.close()
        if hasattr(self, 'transport'):
            self.transport.close()
        info('Connection closed', tag='SFTP')

    def __del__(self):
        try:
            self.close()
        except:
            pass