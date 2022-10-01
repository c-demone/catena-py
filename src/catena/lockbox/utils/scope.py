# share variables between modules and classes

global_scope = {
    'encrypt': None, # Instance of Encryption()
    'db_path': None, # Path to lockbox db
    'config': None,  # Instance of Config()
    'keypair': None, # Instance of RSAKeyPair()
}