import os
from hashlib import sha256

import sqlcipher3
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session

from ..utils.scope import global_scope


sessions = {}

Base = declarative_base()

__all__ = ['get_session', 'drop_sessions', 'get_engine', 'get_db_key', 'get_slashes']

def get_session():
    """
        Return SQLAlchemy session
    """

    global sessions

    if global_scope.get('db_path') is None:
        raise RuntimeError('`db_path` is not defined in the global scope')

    # Create a unique key for the db session
    db_path = global_scope['db_path']

    # Add a session to the current list
    if not sessions.get(db_path):
        sessions[db_path] = Session(bind=get_engine())

    return sessions[db_path]


def drop_sessions():
    """
        Drop current db sessions
    """

    global sessions

    sessions = {}

    return True


def get_engine(encrypted=True):
    """
        return SQLAlchemy engine
    """

    if global_scope['db_path'] is None:
        raise RuntimeError('`db_path` is not defined in the global scope')

    if encrypted:
        return create_engine('sqlite+pysqlcipher://:' + get_db_key() + '@' + get_slashes() + global_scope['db_file'], module=sqlcipher3)
    else:
        return create_engine('sqlite:' + get_slashes() + global_scope['db_file'])


def get_db_key():
    """
        Prepare and return database encryption password
    """

    if global_scope['encrypt'] is None:
        raise RuntimeError('`encrypt` is not defined in the global scope')

    if global_scope['conf'] is None:
        raise RuntimeError('`conf` is not defined in the global scope')

    # Retrieve key
    return sha256(global_scope['encrypt'].key + global_scope['conf'].salt.encode()).hexdigest()


def get_slashes(encrypted=True):
    """
        Return the appropriate number of slash for the database connection
        based on wether the db path is relative or absolute
    """

    if encrypted:
        if os.path.isabs(global_scope['db_path']):
            return '//'

        return '/'
    else:
        if os.path.isabs(global_scope['db_path']):
            return '////'

        return '///'