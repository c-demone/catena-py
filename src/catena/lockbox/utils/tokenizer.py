import jwt
from PyInquirer import prompt
from PyInquirer import style_from_dict
import datetime
from typing import Optional

from .styles import pass_style


def token_prompt():

    questions = [
        {
            'type': 'password',
            'message': 'Enter password for JWT token',
            'name': 'key'
        }
    ]
    
    answers = prompt.prompt(questions, style=pass_style)

    return str(answers.get('key'))


def encode_token_prompt(payload:dict):
    
    key = token_prompt()
    return generate_token(payload, key)


def generate_token(payload:dict, key:str, exp: Optional[int] = 30):
    """
    Generate JWT token with default expiry of 30 minutes
    """
    payload['exp'] = datetime.datetime.now() + datetime.timedelta(minutes=exp)
    return jwt.encode(payload, key, algorithm="HS256")


def decode_token_prompt(token:str):

    key = token_prompt()
    return decode_token(token, key)


def decode_token(token:str, key:str):
    try:
        return jwt.decode(token, key, algorithms="HS256")
    except jwt.ExpiredSignatureError:
        exit("Token expired!")