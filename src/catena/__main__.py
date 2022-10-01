from ..jobs.slurm import SLURMRESTJob
from .lib.yaml_loader import Loader
from .schemas.slurm_submit import SLURMSubmit, SLURMJob
from slurmjobs import run_manifest
import yaml
import sys

if __name__ == '__main__':
    from rich import print
    
    manifest = sys.argv[1]
    jobs = run_manifest(manifest)

    for job in jobs:
        print(f":computer: [chartreuse2]Submitted job: {job}[/chartreuse2]")
