from sqlalchemy import Column, Integer, String

from .db import Base
from ..utils.scope import global_scope


class User(Base):
    __tablename__ = 'user'

    id = Column(Integer, primary_key=True)
    key = Column(String)
    value = Column(String)
