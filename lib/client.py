import os
import sys
import pwd
from pathlib import Path
from typing import Type, Optional
from setuptools.command.easy_install import chmod, current_umask
from os import system
from scp import SCPClient, SCPException
from paramiko import SSHClient, AutoAddPolicy, RSAKey
from paramiko.auth_handler import AuthenticationException, SSHException
from loguru import logger

from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP

# specify logger level formats
logger.add(sys.stderr,
           format="{time} {level} {message}",
           filter="client",
           level="INFO")

logger.add('logs/log_{time:YYYY-MM-DD}.log',
           format="{time} {level} {message}",
           filter="client",
           level="ERROR")


class RSAKeyPair:


    def __init__(self, 
                 privkey:str, 
                 publickey: Optional[str] = None,
                 write: Optional[bool] = True,
                 **kwargs
                ):

        self.__newpriv = False        
        self.__write_keys = write

        self.privkey = Path(privkey)
        
        if publickey is None:
            self.pubkey = Path(privkey).with_suffix('.pub')
        else:
            self.pubkey = Path(publickey)
        
        if kwargs.get('key_context'):
            self.__key_context = True
        

    def __enter__(self):
        try:
            if self.__key_context:
                return self.privkey, self.pubkey
            else:
                return self
        except AttributeError:
            return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


    @property
    def privkey(self):

        return self.__privkey
    

    @privkey.setter
    def privkey(self, p: Type[Path]):

        if p.is_file():
            with p.open(mode='rb') as f:
                # import existing rsa private key
                self.__privkey = self.__import_key(f)
        else:
            self.__newpriv = True

            # generate and set new rsa keypair
            (
             self.__privkey, 
             self.__pubkey
            ) = self.__generate_rsa_keypair(p)
            

    @property
    def pubkey(self):
        return self.__pubkey


    @pubkey.setter
    def pubkey(self, p):
        # file exists and a new private key was not generated
        if p.is_file() and not self.__newpriv:
            with p.open(mode='rb') as f:
                self.__pubkey = self.__import_key(f)
        else:
            # new keypair generated
            pass
                  

    def __import_key(self, f):

        key = f.read()
        return RSA.importKey(key)

    
    def __generate_rsa_keypair(self,
                               p: Type[Path], 
                               bits: Optional[int] = 2048, 
                               export: Optional[bool] = True):
        mask = current_umask()
        key = RSA.generate(bits)
        pubkey = key.publicKey()

        if self.__write_keys:
            with p.open(mode='wb') as priv:
                priv.write(key.exportKey('PEM'))
            chmod(str(p), 0o644 - mask)

        
            with p.with_suffix('.pub').open(mode='wb') as pub:
                pub.write(pubkey.exportKey('OpenSSH'))
            chmod(str(p.with_suffix('.pub')), 0o644 - mask)

        return key, pubkey

    
    def encrypt(self, secret:str):
        cipher = PKCS1_OAEP.new(self.pubkey)
        return cipher.encrypt(secret.encode())
    
    
    def decrypt(self, ciphertext):
        cipher = PKCS1_OAEP.new(self.privkey)
        return cipher.decrypt(ciphertext).decode()
    

    def encrypt_to_file(self, secret, filepath:str):
        encrypted = self.encrypt(secret)
        
        with open(filepath, 'wb') as f:
            f.write(encrypted)
    

    def decrypt_file(self, filepath, to_file=False):
        """
        Decrypt file using GPG key and return as string or 
        write to new decrypted file.
        """

        with open(filepath, 'rb') as f:
            encrypted_data = f.read()
        
        decrypted_data = self.decrypt(encrypted_data)

        if to_file:
            _file = filepath + '.unlocked'
            with open(_file, 'w') as f:
                f.write(decrypted_data)
        else:
            return decrypted_data
    

    def encrypt_file(self, filepath, remove_insecure=True):
        """
        Encrypt an existing file using GPG key ring
        """

        with open(filepath, 'r') as f:
            data = f.read()
        
        encrypted_data = self.encrypt(data)

        _file = filepath + '.locked'
        with open(_file, 'wb') as f:
            f.write(encrypted_data)
        
        if remove_insecure:
            Path(filepath).unlink()


class RemoteClient:

    """
    Remote host Client object to handle connections and actions.
    The Client object is specifically for interacting with a 
    remote host via SSH and SCP using Paramiko
    """

    keypair = RSAKeyPair

    def __init__(self, 
                 host, 
                 user: Optional[str] = pwd.getpwuid(os.getuid()).pw_name,
                 ssh_keydir=None,
                 ssh_pubkey_filename='id_rsa.pub',
                 ssh_privkey_filename='id_rsa',
                 remote_workdir=None):
                 
        self.host = host
        self.user = user
        self.homedir = Path.home()
        if ssh_keydir is None:
            self.ssh_keydir = self.homedir / '.ssh'
        else:
            self.ssh_keydir = Path(ssh_keydir)
    
        self.ssh_pubkey_filename = ssh_pubkey_filename
        self.ssh_privkey_filename = ssh_privkey_filename
        

        self.ssh_pubkey_filepath = self.ssh_keydir / self.ssh_pubkey_filename
        self.ssh_privkey_filepath =self.ssh_keydir / self.ssh_privkey_filename
        
        self.keypair = RSAKeyPair(self.ssh_privkey_filepath, 
                                  self.ssh_pubkey_filepath)

        self.remote_workdir = remote_workdir
        self.remote_keys_accesible = False
        self.client = None
        self.scp = None

        self.__connected = False
    

    def __enter__(self):
        self.__upload_ssh_key()
        return self

    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


    @property
    def privkey(self):
        return self.keypair.privkey


    @property
    def pubkey(self):
        return self.keypair.pubkey


    def __upload_ssh_key(self):
        self.__connect()
        if self.client is not None:
            return 
        else:
            try:
                system(f'ssh-copy-id -i {str(self.ssh_pubkey_filepath)} {self.user}@{self.host}>/dev/null 2>&1')
                logger.info(f'{str(self.ssh_pubkey_filepath)} uploaded to {self.host}')
            except FileNotFoundError as error:
                logger.error(error) 


    def __connect(self):
        """Open connection to remote host."""
        if not self.__connected:
            try:
                self.client = SSHClient()
                self.client.load_system_host_keys()
                self.client.set_missing_host_key_policy(AutoAddPolicy())
                self.client.connect(self.host,
                                    username=self.user,
                                    key_filename=str(self.ssh_pubkey_filepath),
                                    look_for_keys=True,
                                    timeout=5000)
                self.scp = SCPClient(self.client.get_transport())  # For later
            except AuthenticationException as error:
                logger.info('Authentication failed: did you remember to create an SSH key?')
                logger.error(error)
                raise error
            finally:
                self.__connected = True
                return self.client
        else:
            return self.client


    def disconnect(self):
        """
        Disconnect from remote client
        """

        self.client.close()
        self.scp.close()


    def execute_command(self, commands:list) -> None:
        """
        Execute multiple commands on remote client

        Args:
            commands(list): list of commanbds to execute

            >>> e.g. ['cd /var/www/ && ls','ps aux | grep node']

        Commands will be executed in order they are listed
        """
        if self.client is None:
            self.client = self.__connect()


        for cmd in commands:
            stdin, stdout, stderr = self.client.exec_command(cmd)
            stdout.channel.recv_exit_status()
            response = stdout.readlines()
            for line in response:
                logger.info(f'INPUT: {cmd} | OUTPUT: {line}')


    def bulk_dir_upload(self, dirs):
        # a set of paths that are iterated over in a for loop and then __single_dir_upload is run
        if self.client is None:
            self.client = self.__connect()
        uploads = [self.upload_directory(d) for d in dirs]
        logger.info(f'Uploaded {len(uploads)} directories to {self.remote_path} on {self.host}')
    

    def upload_directory(self, source_dir, recursive=True):
        """
        Upload a directory of files. To upload any subdirectories within
        source_dir, leave recursive=True
        """
        for root, dirs, files in os.walk(source_dir, topdown=True):
            logger.info(f'Descending into directory {root}') 
            self.bulk_file_upload([f"{root}/{f}" for f in files])
            if not recursive:
                return [f"{root}/{f}" for f in files]


    def bulk_file_upload(self, files):
        """Upload multiple files to a remote directory."""
        if self.client is None:
            self.client = self.__connect()
        uploads = [self.upload_file(file) for file in files]
        logger.info(f'Uploaded {len(uploads)} files to {self.remote_path} on {self.host}')


    def upload_file(self, file):
        """Upload a single file to a remote directory."""
        try:
            self.scp.put(file,
                         recursive=True,
                         remote_path=self.remote_path)
        except SCPException as error:
            logger.error(error)
            raise error
        finally:
            return file 


    def download_file(self, file):
        """Download file from remote host"""
        if self.client is None:
            self.client = self.__connect()

        self.scp.get(file)


if __name__ == '__main__':
    with RSAKeyPair("/home/mfa/dech/.ssh/id_rsa") as keypair:
        #message = "Hello mello jello"
        #enc_message = keypair.encrypt(message)
        #dec_message = keypair.decrypt(enc_message)
        print(keypair)

    #print(message)
    #print(enc_message)
    #print(dec_message)