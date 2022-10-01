import time
import random
from typing import Optional
from sqlalchemy import or_, func


from PyInquirer import prompt
from PyInquirer import style_from_dict

from .scope import global_scope
from ..models.db import get_session, get_engine
from ..models.secrets import Secrets
from .table import tabulate, clear_screen
from .tokenizer import encode_token_prompt, decode_token_prompt
from .styles import del_style


__all__ = ['all', 'search_to_table', 'count', 'get_by_id', 'get_by_name',
           'get_names', 'add_secret', 'add_secret_from_token', 
           'export_secret_as_token', 'delete_secret', 'delete_prompt',
           'delete_confirm', 'search', 'search_results', 'show_secret']


def all():
    """
        Return a list of all secrets
    """

    return get_session().query(Secrets).order_by(Secrets.id).all()



def search_to_table(rows=[]):
    """
        Transform rows in a table
    """

    # Retrieve id and name
    all_secrets = [[secret.id,  secret.name,
                    secret.url] for secret in rows]

    if len(all_secrets) > 0:
        return tabulate(cols=['ID', 'Name', 'URL'], 
                        rows=all_secrets)
    else:
        return None


def count():
    """
        Return a count of all secrets
    """

    return get_session().query(Secrets).count()


def get_by_id(id_):
    """
        Get a secret by ID
    """

    return get_session().query(Secrets).get(int(id_))


def get_by_name(name:str):
    """
    Return a secret by Name
    """

    secret = get_session().query(Secrets).filter(
        Secrets.name == name).first()
    )

    return secret


def get_names(limit=2000):
    """ Return secret's names for auto-completion """

    results = get_session().query(Secrets.name).\
        filter(Secrets.name != '').\
        limit(limit).\
        all()

    if results:
        return [result.name for result in results]

    return []


def add_secret(name, url='', login='', password='', notes='', category_id=None):
    """
        Create a new secret
    """

    secret = Secrets(name=name,
                         url=url,
                         password=password,
                         notes=notes,
                         category_id=category_id) ## review this --?category_id should stay but how to use
    get_session().add(secret)
    get_session().commit()

    return True


def add_secret_from_token(token):

    decode_secret = decode_token_prompt(token)
    secret = Secrets(**decode_secret)

    get_session().add(secret)
    get_session().commit()
    
    return True


def export_secret_as_token(name):
    """
    Export secret as a JWT token with passphrase
    """

    secret = get_by_name(name)
    secret_token = encode_token_prompt(secret)

    return secret_token
    

def delete_secret(id_: Optional[str] = None,
                  name: Optional[str] = None):
    """
        Delete a secret
    """

    
    if id_ is not None:
        secret = get_session().query(Secrets).filter(
            Secrets.id == int(id_)).first()

    if name is not None:
        secret = get_session().query(Secrets).filter(
            Secrets.name == str(name)).first()        

    if secret:
        get_session().delete(secret)
        get_session().commit()

        return True

    return False


def delete_prompt(entry):

    questions = [
        {
            'type': 'confirm',
            'message': f'Delete the following secret: {entry}?',
            'name': 'delete',
            'default': 'False'
        }
    ]

    return prompt.prompt(questions, style=del_style).get('delete')


def delete_confirm(id_: Optional[str] = None,
                  name: Optional[str] = None):
    """
        Delete a secret (ID is an input, just asking for confirmation)
    """

    entry = None
    if id_ is not None:
        entry = id_
    
    if name is not None:
        entry = name
    # replace with PyImg from autocleus
    if delete_prompt(entry):
        result = delete_secret(id_, name)

        if result is True:
            print()
            print('The secret has been deleted.')

            time.sleep(2)

        return result

    return False


def search(query):
    """
        Search by keyword
    """

    query = '%' + str(query) + '%'

    return get_session().query(Secrets) \
        .filter(or_(Secrets.name.like(query), 
                    Secrets.url.like(query),
                    Secrets.id.like(query))) \
        .order_by(Secrets.id).all()



def search_results(rows):
    """
        Display search results
    """

    print()
    print(to_table(rows))
    print()

    # Ask user input
    input_ = menu.get_input(
        message='Select a result # or type any key to go back to the main menu: ')

    if input_:
        try:
            result = [row for row in rows if row.id == int(input_)]

            if result:
                return item_view(result[0])
        except ValueError:  # Non integer
            pass

    return False



def show_secret(item):
    """
        Show a secret for X seconds and erase it from the screen
    """

    try:
        print("* The password will be hidden after %s seconds." %
              (global_scope['conf'].hideSecretTTL))
        print('* The password is: %s' % (item.password))

        time.sleep(int(global_scope['conf'].hideSecretTTL))
    except KeyboardInterrupt:
        # Will catch `^-c` and immediately hide the password
        pass

    clear_screen()
    print('* The password is: ' + '*' * (
        len(item.password) + random.randint(1, 8)))