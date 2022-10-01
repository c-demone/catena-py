from .utils.scope import global_scope as gs
from .utils.config import Config
from .utils.security import Encryption
from .utils.styles import pass_style
from .utils.session import create_db, validation_key_new


from PyInquirer import prompt

__all__ = ['_lockbox_setup', '_load_config', '_load_encrypt',
           'key_prompt', 'interactive_start']

           
def _lockbox_setup():

    # create lockbox database if not exists
    create_db()

    # create a validation key
    validation_key_new()


def _load_config(conf: Type[Config], dbpath:str):
    gs['conf'] = conf
    gs['db_path'] = dbpath
    return gs


def _load_encrypt(crypt: Type[Encryption]):
    gs['encrypt'] = crypt
    return gs


def key_prompt():

    questions = [
        {
            'type': 'password',
            'message': 'Enter master key for LockBox',
            'name': 'key'
        }
    ]
    
    answers = prompt.prompt(questions, style=pass_style)

    return str(answers.get('key'))



def interactive_start():
    """
    Start LockBox interatively
    # https://questions.readthedocs.io/en/latest/readme.html
    #
    """
    return None


