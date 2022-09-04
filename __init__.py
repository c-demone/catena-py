from pathlib import Path
from typing import Optional
import sys
import os

from .jobs.slurm import SLURMRESTJob
from .lib.yaml_loader import Loader, safe_loader
from slurmjobs.schemas import JobManifest, SLURMSubmit, SLURMJob
import slurmjobs.lib.env as env
from slurmjobs.jobs import Jobs



def run_manifest(manifest:str, _submit:Optional[bool]=True):
    """
    Run a series of jobs defined in a yaml manifest.

    Arguments:
    
        manifest: path to yaml file containin manifest
        
        _submit: whether to submit job or not. Default is True. If false
                    returns list of job objects, which can be submitted at 
                    a later time by calling each job objects submit method.
    """
    # initialize jobs list
    #jobs = []
    jobs = Jobs()

    # allow including variables from other yamls
    Loader.add_constructor('!include', Loader.include)

    # check if manifest path is an absolute path or not and assign main manifest var
    ppath = Path(manifest)
    if not ppath.is_absolute():
        cpath = Path(sys.argv[0])

        # if being invoke from python script and not notebook
        if (Path(cpath.resolve()).is_file() and 
           'site-packages' not in sys.argv[0].split(os.path.sep)):
            
            manifest = Path(Path(cpath.resolve()).parent) / manifest
            ppath = Path(manifest)
        
        env.CONTEXT_ROOT = Path(ppath.resolve()).parent
        manifest = Path(env.CONTEXT_ROOT) / Path(manifest).name

    else:
        env.CONTEXT_ROOT = ppath.parent

    # read manifest
    with open(manifest, 'r') as f:
        data = safe_loader(f, Loader=Loader)
        
    # when using !include end up with list of lists for jobs
    if isinstance(data['jobs'][0], list): 
        data['jobs'] = [x for y in data['jobs'] for x in y]
    else:
        pass

    # same for job_options
    try:
        job_opts = data.get('job_options')[0]
        if isinstance(job_opts, list):
            data['job_options'] = [x for y in data['job_options'] for x in y]
        else:
            pass
    except Exception:
        pass

    jobdefs = JobManifest(**data).expand_jobs()
    for jobdef in jobdefs:

        with SLURMRESTJob(env_modules=jobdef.env_modules, 
                          job_script=jobdef.job_script,
                          job_script_args=jobdef.job_script_args,
                          command=jobdef.command,
                          env_extra=jobdef.env_extra, 
                          **jobdef.job.dict(exclude_none=True)) as job:
            jobs.append(job)

            if _submit:
                jobs.submit()

    return jobs