from pydantic import BaseModel, validator
from typing import (List, Optional, 
                    Dict, Any, Literal, Union)
from collections import namedtuple
from pathlib import Path

from .slurm_submit import SlurmSubmit
from . import ExtendedBaseModel
from rich import print


"""
Job dependency type.

Attributes:
    type: type of dependency, where dependencies can be 
        * after: after the specified job has started
        * afterany: after the specified job has terminated 
        * afterok: after the specified job has finished with exit code of zero
        * afternotok: after the specfied job has finished with non-zero exit code
        * singleton: after all previously launched jobs of the same name and user have ended.
"""
DependencyType = Literal['after', 'afterany', 'afterok', 'afternotok', 'singleton']

class JobOptions(SlurmSubmit):
    """
    Job options schema for job manifest. Extends SlurmSubmit which
    provides attributes corresponding to sbatch options in SLURM. 
    
      
    Attributes:
        name: job name as it will appear in SLURM queue (the __root__ key of a
            given Job is usually set internally as the job name when parsing a manifest)

        env_modules: list module names that should be loaded when submitting the job
            to a SLURM scheduler and made available to the environment running the job. 
            For example,  `['anaconda3/2021.11', 'matlab/96']`
        
        env_extra: dictionary of extra environment variables to export to the
            environment running the job submitted to a SLURM scheduler. For
            example, `{'MYVAR': '/path/to/stuff'}`. See how to 
            [append, prepend, or replace](../examples/example1.md#env_extra_feats)

        job_script: path to the script, either relative or absolute. The `~` is
            also excepted and converted to the appropriate absolute path for the 
            current users directory. ***If*** using relative paths, be sure to
            understand where the paths should be relative to, to appropriately
            locate your scripts.
        
        job_script_args: list of arguments to pass to the job_script when
            it is executed. For example, `job_script_args=['--version']`
        
        command: custom command to use when running `job_script`. If defined, the
            the script provided will be run as an executable with this command
            prepended. For example, command='python -m' would result in the
            `job_script` being called as: `python -m <job_script>`. Generally,
            the default should give the right result.
    """
    name: Optional[str]
    env_modules: Optional[List[str]] = None
    env_extra: Optional[Dict[str, Any]] = None
    job_script: Optional[str]
    job_script_args: Optional[List[str]] = None
    command: Optional[str]
    dependencies: Optional[Dict[DependencyType, Union[str, List[str]]]]

    @validator('job_script')
    def expand_home_shortcut(cls, v):
        if v is not None:
            if str(v.startswith('~')):
                ppath = Path(v)
                return str(ppath.expanduser())
            else:
                return v
        else:
            return v


class JobDefinition(JobOptions):
    """
    Local job definition that extends JobOptions as well as provides
    a field, job, for referencing global JobOptions (using YML
    anchors/aliases)

    Attributes:

        job: global job options parsed from YML anchors/aliases. Ultimately local
            and global job options are combined when defining a given Job to be 
            submitted to a SLURM cluster, with local job options taking precendence
            over global

    """
    job: Optional[JobOptions]



class Job(BaseModel):
    __root__: Dict[str, JobDefinition]


class JobManifest(ExtendedBaseModel):
    """
    Model for parsing job manifests: describes the expected layout of a job manifest
    and provides methods for returning job definitions that can be used to initialize
    a `slurmjobs` job instance (currently, SlurmJob)
      
    TODO: Add validator to ensure that depencies for a job do not list the job itself
          as a dependency.

    Attributes:
        job_options: section of YML job manifest for defining global job options as a list.
            Global job options are tagged using anchors and referenced within a given job's
            job definition, under the `job` field. All job options that 

        jobs:  list of instances of JobDefinition 

    """
    cluster_profile: str
    catena_config: Optional[str] = str(Path().home() / '.catena/conf.yml')
    version: Optional[str] = "1.0"
    job_options: Optional[List[JobOptions]]
    jobs: Optional[List[Job]]
    
    class Config:
        """
        `JobManifest` model `Config` sub-class: can be accessed internally
        as `self.Config` or `JobManifest.Config`. The config class of a Pydantic model is also
        passed as a kwarg to validators and acts as a useful means of 
        storing external variables that are accesible to field 
        validators.

        Attributes:
            ext_opts: extra job options that are separate from SLURM job options.
                This difference is abstracted to the user, but is managed
                internally.
        """
        ext_opts: list = ['env_modules', 
                          'job_script',
                          'env_extra',
                          'job_script_args',
                          'command',
                          'dependencies']


    def __filter_ext_opts(self, jobdef: JobOptions, field: str):
        """
        Filter non sbatch options from job (global opts) field. Local
        job opts will always take precedence over those defined globally
        """

        field_val = None
        if (jobdef.job.dict().get(field) is not None and 
            jobdef.dict().get(field) is not None):
            field_val = jobdef.pop(field)
            jobdef.job.pop(field)

        elif jobdef.job.dict().get(field) is not None: #and
              field_val = jobdef.job.pop(field)

        else:
            field_val = jobdef.pop(field)
        
        return jobdef, field_val


    def expand_jobs(self):
        """
        Return list of job definitions processed from a initialized instance
        of `self` or `JobManifest`. The fields defined within this model can
        be passed to an instance of a `slurmjobs` Job. For example, the 
        [SLURMRESTJob](../jobs/slurmrestjob.md) object.
        """
        jobs = []
        filtered_opts = {}

        # iterate over all job definitions
        for jobblock in self.jobs:

            for jobname, jobdef in jobblock.__root__.items():

                # create named tuple for storing unset/set options and there default values
                Options = namedtuple('Options', 'name default')     
                
                # collect set job options on local and global levels
                local_opts_set = jobdef.__fields_set__
                global_opts_set = jobdef.__fields_set__
                fields = jobdef.job.__fields__

                # set job name
                jobdef.name = jobname

                # create copy of job excluding env_modules property
                tmpjob = JobOptions(**{k:v for k,v in jobdef.job.dict().items() 
                                           if k != 'env_modules'})
                tmpjob = JobOptions(**jobdef.job.dict())

                # filter external options
                for optname in self.Config.ext_opts:
                    jobdef, optval = self.__filter_ext_opts(jobdef, optname)
                    filtered_opts[optname] = optval

                # list all set field names and default values for non-required fields      
                setfields = [Options(x, fields[x].default) for x in fields.keys() if x in 
                                global_opts_set]

                for opt in setfields:
                    if opt.name in jobdef.dict():
                        tmpjob[opt.name] = jobdef.pop(opt.name)
                
                # add ext opts back into job def
                for optname, optval in filtered_opts.items():
                    jobdef[optname] = optval
                    tmpjob.pop(optname)

                # set job properties after filtering
                jobdef['job'] = tmpjob
                jobs.append(jobdef)
                
        return jobs         