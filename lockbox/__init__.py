from .lockbox import *

# crud methods and utilities
from .utils.secrets import *
from .utils.session import *
from .utils.table import tabulate
from .lockbox import *

# models
from .models.db import *
from .models.secrets import Secrets
from .models.session import User

# collect methods to include in LockBox()
__methods__ = {k: v for k,v in locals().items() 
                        if not k.startswith('__')}

# other utilities
from .utils.styles import pass_style
from .utils.config import Config
from .utils.security import Encryption, GPGKeyRing

from pathlib import Path
from typing import Optional

# defaults
conf_dir = Path.home() / '.lockbox'
conf_file = conf_dir / '.lockbox.yml'
dbpath = conf_dir /'.lockbox.db'


class LockBox:

    def __init__(self, password: Optional[str] = None):

        self.conf_dir = conf_dir
        self.dbpath = dbpath

        # create/load configuration for lockbox
        self.scope = _load_config(Config(conf_dir=str(self.conf_dir)),
                                dbpath=str(self.dbpath))

        self.__keyfile = self.conf_dir / '.lockbox.key'
        self.key = password

        # load a shared instance of Encryption() with key
        self.scope = _load_encrypt(Encryption(key=self.key))

        # set state of lockbox
        self.unlocked = False


    def __getattr__(self, name):
        """
        Class attribute getter, that will dynamically add 
        methods imported into this script from other modules 
        (__methods__) as a method of this class when called. 
        Allows importing all crud methods into this main script 
        and upon initializing an instance of LockBox these methods 
        can be dynamically accessed from the class instance.

        Usage:

        lb = LockBox()

        # call lockbox.utils.secrets.add_secret_from_token method:
        lb.add_secret_from_token(token)
        """
        if name not in self.__dict__:
            if name in __methods__:
                return __methods__.get(name)
        
        return self.__dict__.get(name)

    
    def __setattr__(self, name, val):

        self.__dict__[name] = val

    
    def __enter__(self):
        return self


    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


    @property
    def unlocked(self):
        return self.__unlocked


    @unlocked.setter
    def unlocked(self, state:bool):

        if not self.dbpath.is_file():
            # lockbox doesn't exist
            _lockbox_setup()

        self.__unlocked = state

        if not self.__unlocked and self.lock:
            drop_sessions()
            return self.__unlocked()

        if validation_key_validate(self.key):
            self.__unlocked = True
        
        else:
            self.__unlocked = False

        return self.__unlocked


    @property
    def lock(self):
        return self.__lock


    @lock.setter
    def lock(self, state:Optional[bool]=False):
        self.__lock = state


    @property
    def key(self):
        return self.__key


    @key.setter
    def key(self, password: Optional[str] = None):
        """
        Masterkey to unlock LockBox
        """

        # create randomly generated password if not set
        if password is None:
            if not self.__keyfile.is_file():
                self.__key = pw(min_word_length=12, max_word_length=15)
            else:
                self.__key = self.scope.get('keyring').decrypt_file(
                                                            str(self._keyfile))
        
        # save password to encrypted file if not exists already
        if not self.__keyfile.is_file():
            self.scope.get('keyring').encrypt_to_file(password, 
                                                      str(self._keyfile))


    def close(self):

        self.lock = True
        self.unlocked = False

        return True