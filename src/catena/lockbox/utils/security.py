import os
import base64
import string
import pwd
from random import randint, choice
from typing import Optional, Dict, Any
from pathlib import Path

from Crypto.Cipher import AES
from Crypto.Hash import SHA256
from Crypto import Random as CryptoRandom
from yaspin import yaspin
import gnupg

from .scope import global_scope as gs


class GPGKeyRing:


    def __init__(self, 
                 homedir: str,
                 user: Optional[str] = pwd.getpwuid(os.getuid()).pw_name,
                 keyinput: Optional[Dict[str, Any]] = None
                ):

        self.key = None
        self.homedir = homedir
        self.__current_flag = '@lockbox_current@'

        # create directory if it doesn't already exist
        Path(self.homedir).mkdir(parents=True, exist_ok=True)
        
        # initiate key ring
        self.user = user
        self.gpg = gnupg.GPG(gnupghome=self.homedir)
        self.default_key_input = keyinput
        
        # initialize keyring: defines self.key, self.key_input
        self.__initialize_keyring()
        
    
    def __enter__(self):
        return self
    

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


    @property
    def key_exists(self):
        
        try:
            uids = self.gpg.list_keys()[0].get('uids')
            if self.user in uids[0]:
                return True

        except IndexError:
            return False


    @property
    def default_key_input(self):
        return self.__input
    

    @default_key_input.setter
    def default_key_input(self, inp:Optional[dict] = None):
        
        input = {
                 'name_real': self.user,
                 'name_comment': self.__current_flag,
                 'key_type': 'RSA',
                 'key_length': 4096,
                 'key_usage': '',
                 'subkey_type': 'RSA',
                 'subkey_length': 4096,
                 'subkey_usage': 'encrypt,sign,auth'
                }

        if inp is not None:
            self.__input = inp
        else:
            self.__input = input
    

    @property
    def fingerprint(self):
        if self.key is not None:
            return self.key.fingerprint
        else:
            return None
    

    def __initialize_keyring(self):
        with yaspin(text="Initializing keyring", color='yellow') as sp:
            if not self.key_exists:
                self.key_input = self.gpg.gen_key_input(**self.default_key_input)
                self.key = self.gpg.gen_key(self.key_input)
            else:
                self.key_input = self.gpg.gen_key_input()
                self.key = self.gpg.gen_key(self.key_input)
            
            sp.ok("🔏 Keyring Initialized")
        return self.key


    def get_key(self):
        """
        Key getter that returns None if key doesn't exist
        """

        if self.key_exists and self.key is None:
            with yaspin(text='Retrieving Keyring', color='cyan') as sp:
                self.key_input = self.gpg.gen_key_input()
                self.key = self.gpg.gen_key()
                sp.ok("🔏 Retrieved Keyring")

        return self.key


    def encrypt(self, message):
        """
        Encrypt string using GPG key ring
        """
        return str(self.gpg.encrypt(message, self.fingerprint))
    

    def decrypt(self, encrypted_data):
        """
        Decrypt string using GPG key ring
        """
        return self.gpg.decrypt(str(encrypted_data))


    def encrypt_to_file(self, message, filepath):
        """
        Encrypt string using GPG key ring and write to file
        """
        encrypted_data = self.encrypt_to_file(message)
        with open(filepath, 'wb') as f:
            f.write(encrypted_data)


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


class Encryption:

    def __init__(self, key:Optional[str] = None):

        self.key = key  # Key in bytes
        self.salted_key = None  # Placeholder for optional salted key
    

    def digest_key(self):
        """
            Use SHA-256 over our key to get a proper-sized AES key
        """

        # Add optional salt to key
        key = self.key
        if self.salted_key:
            key = self.salted_key

        return SHA256.new(key).digest()

    def get_aes(self, IV):
        """
            AES instance
        """

        return AES.new(self.digest_key(), AES.MODE_CBC, IV)

    def gen_salt(self, set_=True):
        """
            Generate a random salt
        """

        min_char = 8
        max_char = 12
        allchar = string.ascii_letters + string.punctuation + string.digits
        salt = "".join(choice(allchar)
                       for x in range(randint(min_char, max_char))).encode()

        # Set the salt in the same instance if required
        if set_:
            self.set_salt(salt)

        return salt

    def set_salt(self, salt=None):
        """
            Add a salt to the secret key for this specific encryption or decryption
        """

        if salt:
            self.salted_key = salt + self.key
        else:
            self.salted_key = None

    def encrypt(self, secret):
        """
            Encrypt a secret
        """

        # generate IV
        IV = CryptoRandom.new().read(AES.block_size)

        # Retrieve AES instance
        aes = self.get_aes(IV)

        # calculate needed padding
        padding = AES.block_size - len(secret) % AES.block_size

        # Python 2.x: secret += chr(padding) * padding
        secret += bytes([padding]) * padding

        # store the IV at the beginning and encrypt
        data = IV + aes.encrypt(secret)

        # Reset salted key
        self.set_salt()

        # Return base 64 encoded bytes
        return base64.b64encode(data)

    def decrypt(self, enc_secret):
        """
            Decrypt a secret
        """

        # Decode base 64
        enc_secret = base64.b64decode(enc_secret)

        # extract the IV from the beginning
        IV = enc_secret[:AES.block_size]

        # Retrieve AES instance
        aes = self.get_aes(IV)

        # Decrypt
        data = aes.decrypt(enc_secret[AES.block_size:])

        # pick the padding value from the end; Python 2.x: ord(data[-1])
        padding = data[-1]

        # Python 2.x: chr(padding) * padding
        if data[-padding:] != bytes([padding]) * padding:
            raise ValueError("Invalid padding...")

        # Reset salted key
        self.set_salt()

        # Remove the padding and return the bytes
        return data[:-padding]



if __name__ == '__main__':

    msg = 'hello world!'
    with GPGKeyRing(homedir='/home/mfa/dech/GNUPGTEST2') as gpg:
        enc_msg = gpg.encrypt(msg)
        print(enc_msg)
        dec_msg = gpg.decrypt(msg)
        print(dec_msg)

        gpg.encrypt_to_file(msg, '/home/mfa/dech/enc_test.txt')
