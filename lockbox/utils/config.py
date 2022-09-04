import os
from Crypto.PublicKey import RSA
import yaml
from uuid import uuid4
from typing import Optional
from pathlib import Path
import confuse
from confuse.sources import ConfigSource
from confuse.core import Configuration
from confuse.exceptions import ConfigReadError
from confuse import yaml_util
from fs.memoryfs import MemoryFS
from typing import Type

from .scope import global_scope
from slurmjobs.lib.client import RSAKeyPair


conf_file = 'lockbox.yml'
__lockbox = '.lockbox'

DEFAULT_FILENAME = 'config_default.yaml'
CONFIG_FILENAME = 'config.yaml'


def load_yaml(filename, keypair: Type[RSAKeyPair], loader=yaml_util.Loader, mem=MemoryFS()):
    """Read a YAML document from a file. If the file cannot be read or
    parsed, a ConfigReadError is raised.
    loader is the PyYAML Loader class to use to parse the YAML. By default,
    this is Confuse's own Loader class, which is like SafeLoader with
    extra constructors.

    Adapted from PyPi confuse

    Use in memory filesystem to store decrypted file

    """
    
    # decrypt file
    with open(filename, 'rb') as f:
        enc_data = f.read()
    data = keypair.decrypt(enc_data)

    # write data to file in memory
    with mem.open('tmp_config.yml', 'w') as mf:
        mf.write(data)
    
    # delete the decrypted data
    del data
    
    try:
        with mem.open('tmp_config.yml', 'rb') as f:
            return yaml.load(f, Loader=loader)
    except (IOError, yaml.error.YAMLError) as exc:
        raise ConfigReadError('tmp_config.yml', exc)


class SecureYamlSource(ConfigSource):

    def __init__(self, 
                 keypair,
                 filename=None,
                 default=False, 
                 base_for_paths=False,
                 optional=False, 
                 loader=yaml_util.Loader):

        self.keypair = keypair
        
        self.__path = Path(filename)
        self.filename = str(self.__path.resolve())
        super(SecureYamlSource, self).__init__({}, filename, default, base_for_paths)
        self.loader = loader
        self.optional = optional
        
        self.load()


    def load(self):
        """
        Load YAML data from the source's filename.
        """
        if self.optional and not os.path.isfile(self.filename):
            value = {}
        else:
            value = load_yaml(self.filename, self.keypair, loader=self.loader) or {}
        self.update(value)  


class SecureConfiguration(Configuration):
    """
    Adapted from confuse.Configuration. Replacing YamlSource by
    SecureYamlSource
    """
    
    def __init__(self, appname, keypair=None, modname=None, read=True,
                 loader=yaml_util.Loader):

        super().__init__(appname, modname, read, loader)
        
        self.keypair = keypair
    

    @property
    def keypair(self):
        return self.__keypair
    

    @keypair.setter
    def keypair(self, value: Type[RSAKeyPair]):
        self.__keypair = value


    def _add_user_source(self):
        """Add the configuration options from the YAML file in the
        user's configuration directory (given by `config_dir`) if it
        exists.
        """
        filename = self.user_config_path()
        self.add(SecureYamlSource(filename, self.keypair, loader=self.loader, optional=True))

    def _add_default_source(self):
        """Add the package's default configuration settings. This looks
        for a YAML file located inside the package for the module
        `modname` if it was given.
        """
        if self.modname:
            if self._package_path:
                filename = os.path.join(self._package_path, DEFAULT_FILENAME)
                self.add(SecureYamlSource(filename, self.keypair, loader=self.loader,
                                    optional=True, default=True))


    def set_file(self, filename, base_for_paths=False):
        """Parses the file as YAML and inserts it into the configuration
        sources with highest priority.
        :param filename: Filename of the YAML file to load.
        :param base_for_paths: Indicates whether the directory containing the
            YAML file will be used as the base directory for resolving relative
            path values stored in the YAML file. Otherwise, by default, the
            directory returned by `config_dir()` will be used as the base.
        """
        self.set(SecureYamlSource(filename, self.keypair, base_for_paths=base_for_paths,
                            loader=self.loader))
    

    def reload(self):
        """Reload all sources from the file system.
        This only affects sources that come from files (i.e.,
        `YamlSource` objects); other sources, such as dictionaries
        inserted with `add` or `set`, will remain unchanged.
        """
        for source in self.sources:
            if isinstance(source, SecureYamlSource):
                source.load()


class Config:

    conf = SecureConfiguration("lockbox")

    def __init__(self,
                 conf_dir: Optional[str] = None):
        
        self.conf_dir = conf_dir
            
        if self.conf_dir is None:
            self.conf_dir = Path.home() / __lockbox
        else:
            self.conf_dir = Path(conf_dir)
        
        # create conf directory and parents if not exists
        self.conf_dir.mkdir(parents=True, exist_ok=True)

        keydir = self.conf_dir / '.keys'

        self.keypair = RSAKeyPair(privkey=str(keydir / 'id_lockbox'))
        global_scope['keypair'] = self.keypair

        self.conf.keypair = self.keypair
        self.__check_config()
    

    def __str__(self):
        """
        String representation of config that allows external
        save/write functions to be applied:

        f.write(Config())
        """
        return self.conf.dump()


    def __getattr__(self, name):
        """
        Allows calling config values directly:

        conf = Config()
        conf.salt
        """
        try:
            return self.conf['lockbox'][name].get()
        except KeyError:
            return None
        
    
    def __check_config(self):
        
        if not (self.conf_dir / 
                conf_file).is_file():
            (self.conf_dir / conf_file).touch(mode=600)            
            self.set_default_config_file()
            self.__check_config()
        
        # this reads in configuration
        self.conf.set_file(str(self.conf_dir / conf_file))


    def set_default_config_file(self):
        """
            Set a user default config file
        """

        self.config['lockbox'] = {
            'version': '0.1',
            'keyVersion': '1',  # Will be used to support legacy key versions if the algorithm changes
            'salt': self.generate_random_salt(),
            'clipboardTTL': '15',
            'hideSecretTTL': '5',
            'autoLockTTL': '900',
            'encryptedDb': True,
        }

        self.save()
        

    def update(self, name, value, hard=False):
        """
        Update a given property value by name
        """

        self.conf['lockbox'][name] = str(value)

        if hard:
            self.save(overwrite=True)


    def save(self, overwrite=False):
        with (self.conf_dir / 
             conf_file).open(mode='wb') as f:

            if overwrite:
                f.seek(0)
                f.write(self.keyring.encrypt(self.conf.dump()))
                f.truncate()
            else:
                f.write(self.keyring.encrypt(self.conf.dump()))


    def generate_random_salt(self):
        """
            Generate a random salt
            Will be used to generate the vault hash with the user master key
        """

        return str(uuid4())


    def get_config(self):
        """
            Will return a user config and set a default if necessary
        """

        # default config generated if needed in __init__
        return self.conf['lockbox'].get()


if __name__ == '__main__':

    # generate keyring and encrypted lockbox conf file
    config = Config(conf_dir='/home/mfa/dech/CONFTEST')
