"""
A first example to show how the SlurmJob object is used to define and submit
a job to a SLURM cluster.

The **kwargs SlurmJob can be found defined in models.slurm_submit.SlurmSubmit
These are the SLURM SBATCH options.

SlurmJob also has some kwargs of interest, notably:
    >> job_script: path to the script you want to run
    >> name: name of your job in slurm
    >> profile: 
    >> env_modules: list of environment modules to load into your jobs environment
                    (should provide name for module as it appears when doing 
                     'module list')


rich is a great library for nicely printing things to the console. The inspect method 
is used here to expose what the class looks like and what it contains before and after
submitting a job

NOTE: To run this script and have it submit a job, you should add the -s flag
    e.g: python3 slurm_job1.py -s
"""
import sys
from pathlib import Path
from rich import inspect



sys.path.append(str(Path(*list(Path(__file__).parent.resolve().parts[:-2]))/"src"))

from catena.jobs.slurm import SlurmJob
from catena.models.config import CatenaConfig

conf = CatenaConfig.read()

home = str(Path.home())

job = SlurmJob(name='slurmjobs_example1',
               profile='my_slurm_cluster1',
               job_script="../scripts/hello_world",
               env_extra={'NAME': 'Christopher'},
               standard_out='~/go_hello_world.out',
               standard_error='~/go_hello_world.err',
               tasks=1,
               cpus_per_task=1,
               memory_per_node='1GB',
               env_modules=['go/1.18.6']
               )
                
inspect(job)

if '-s' in sys.argv:
    print("submitting job")
    job.submit()

    inspect(job)

