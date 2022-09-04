from ..models.db import Base, get_session, get_engine, drop_sessions
from ..models.secrets import Secrets
from ..models.session import User
from .scope import global_scope as gs

__all__ = ['create_db', 'validation_key_new', 'validation_key_rekey',
           'validation_key_validate']


def create_db():
    """
    Create database
    """

    session = get_session()
    Base.metadata.create_all(get_engine())
    session.commit()


def validation_key_new():
    """
        Create a validation key
    """

    key_salt = gs['encrypt'].key + \
        gs['conf'].salt.encode()

    # Save user
    user = User(key='key_validation',
                     value=gs['encrypt'].encrypt(key_salt))
    get_session().add(user)
    get_session().commit()


def validation_key_validate(key):
    """
        Verify if a validation key is valid
    """

    # validation key from database
    try:
        user = get_session().query(User).filter(
            User.key == 'key_validation').order_by(User.id.desc()).first()
    except exc.DatabaseError:  # In case of encrypted db, if the encryption key is invalid
        # Drop db sessions to force a re-connection with the new key
        drop_sessions()

        return False

    # Concatenate user given key and config's salt
    key_salt = key + gs['conf'].salt.encode()

    # Key is valid
    try:
        if gs['encrypt'].decrypt(user.value) == key_salt:
            return True
    except ValueError:  # Decryption error
        return False

    return False


def validation_key_rekey(newenc):
    """
        Replace a validation key with a new master key
    """

    # Get validation key
    user = get_session().query(User).filter(
        User.key == 'key_validation').order_by(User.id.desc()).first()

    if user:
        key_salt = newenc.key + \
            gs['conf'].salt.encode()

        # Update validation key
        user.value = newenc.encrypt(key_salt)

        get_session().add(user)
        get_session().commit()

        return True

    return False