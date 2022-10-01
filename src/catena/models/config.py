from pydantic import BaseModel, Extra, validator
from typing import List, Optional, Dict
from rich import print
from pathlib import Path

from . import ExtendedBaseModel
from ..lib.yaml_loader import Loader, safe_loader

#TODO: Base Cluster class with ABC abstract methods
#class BaseCluster(ABC) -> SlurmCluster(BaseCluster, BaseModel)

class SlurmCluster(BaseModel):
    api_host: str
    api_proto: Optional[str] = 'http'
    api_version: Optional[str] = '0.0.35'
    api_port: Optional[str] = '6820'

    class Config:
        api_version_compat = ['0.0.35']


class ClusterDefinition(BaseModel):
    backend: Optional[str] = 'slurm'

    class Config:
        extra = Extra.allow
        arbitrary_types_allowed = True

    def __init__(self, **kwargs):

        super().__init__(**kwargs)

        cluster_args = {k: v  for k, v in kwargs.items() if k not in self.__fields__}
        
        if self.backend == 'slurm':
            slurm_cluster = SlurmCluster(**cluster_args)
            for attr, val in slurm_cluster.dict().items():
                self.__dict__[attr] = val

            self._cluster = slurm_cluster
                

class Cluster(BaseModel):
    """
    Cluster definition with dynamic root entry which corresponds
    to cluster profile name or key that it can be called by
    """
    __root__: Dict[str, ClusterDefinition]


class CatenaConfig(ExtendedBaseModel):
    version: Optional[str] = 1.0
    clusters: Optional[Dict[str, ClusterDefinition]] = {}


    @classmethod
    def read(cls, path:Optional[str] = None):
        """
        Read configuration from specified yaml file
        """
        if path is None:
            path = Path.home() / ".catena/conf.yml"
        
        if not Path(path).is_file():
            print(f"⚠️ [red]file does not exist: {path}[/red]")
            exit(1)
        
        # read manifest
        with open(path, 'r') as f:
            data = safe_loader(f, Loader=Loader)
        
        return cls(**data)


    def cluster_profiles(self):
        """
        Returns available cluster profiles defined in catena configuration
        file
        """
        return list(self.clusters.keys())


    def get_cluster(self, name:str):
        """
        Return configuration properties for the named cluster profile
        """
        if name in self.clusters:
            return self.clusters.get(name)

        print(f"⚠️ [red]profile '{name}' does not exist[/red]")
        print(f"Possiblities include: {self.cluster_profiles()}")