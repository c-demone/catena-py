from pydantic import BaseModel
from typing import Any, no_type_check


class ExtendedBaseModel(BaseModel):

    @no_type_check
    def __setitem__(self, name: str, value: Any):
        """
        Dunder method for allowing setting attributes dictionary style
        
        Args:
            name: name of attribute to set
            value: value to set attribute to
        """
        self.__setattr__(name, value)
    
    @no_type_check
    def __eq__(self, other):
        """
        Dunder method for allowing comparison of Options instances. If
        two instances are the same will return True
        Args:
            other: other instance of Options to compare with
        """

        # do not compare against unrelated types
        if not isinstance(other, Options):
            return NotImplemented
        return self.dict() == other.dict()


    def setdefault(self, keyname: str, value: Any):
        """
        Analogue to `dict.setdefault(keyname, value)` for Pydantic models
        Will set the value of the corresponding attribute, `keyname` if it has not been set
        
        Args:
            keyname: name of attribute to set default value for
            value: value to set if attribute has not been set to a non-default value already
        """
        if keyname not in self.__fields_set__:
            self[keyname] = value
            return value
        else:
            return self.dict().get(keyname)


    def pop(self, keyname: str, value: Any=None):
        """
        Analogue to `dict.pop(keyname, value)` for Pydantic models
        
        Will remove the attribute from the model and return it's value if it has been set,
        otherwise it will return `value`
        Args:
            keyname: name of attribute to remove and return it's value
            value: value to return if `keyname` attribute has not been set to a non-default value
        
        """
        _val = self.dict().pop(keyname, value)
        delattr(self, keyname)

        if _val is None:
            return value
        else:
            return _val


    def get(self, keyname: str, value: Any=None):
        """
        Analogue to `dict.get(keyname, value)` for Pydantic models
        Args:
            keyname: name of attribute for which to return the corresponding value
            value: value to return if `keyname` attribute has not been set to a non-default value
        """
        if keyname not in self.__fields__set__:
            return value
        else:
            return self.dict().get(keyname)
