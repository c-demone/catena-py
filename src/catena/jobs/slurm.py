import os
import sys
import pwd
from typing import Optional, Dict, List, Callable, Any, Union
import requests
import importlib.resources as pkg_resources
from pathlib import Path

import catena.lib as lib
from catena.models.job_manifest import DependencyType
from ..models import SlurmSubmit, SlurmCluster, SlurmModel
from catena.lib import env, _read_code, ContextTree
from catena.lib.scripts import JobScript
from subprocess import Popen, PIPE
import errno
import time
from loguru import logger
import subprocess
import json
from rich import inspect


# specify logger level formats
logger.add('logs/log_{time:YYYY-MM-DD}.log',
           format="{time} {level} {message}",
           level="INFO")

logger.add('logs/log_{time:YYYY-MM-DD}.log',
           format="{time} {level} {message}",
           level="ERROR")

# initialize module command
mod_init = pkg_resources.read_text(lib, 'modulecmd.py')
exec(mod_init)

class SlurmJob:
    
    """
    The `SLURMRESTJob` is the most basic type of job in the `slurmjobs` library.

    The `SLURMRESTJob` class provides a dynamic object for storing all information 
    required to launch a job through the SLURM REST API programmatically, in
    Python. This type of SLURM `Job` is *best suited* for orchestrating work
    through the SLURM scheduler ***locally***, meaning this class is best used
    in a script run on an HPC cluster with SLURM as the scheduler.

    *This class is meant to be extended by other job types*

    Attributes:
        job_options: [SLURMSubmit](../schemas/slurm_job_schemas.md#slurm_submit) model 
            containing all SLURM sbatch options

        name: SLURM job name, used to define the attribute of the same name in 
            `job_options`
        
        user: user-id of the user initializing this class. This will default to the
            user that has called this class (i.e you). 
        
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
        
        jwt_lifespan: amount of time in seconds for which the SLURM JWT token
            should be valid. The token is used to authenticate a given user
            when receiving requests, and expects that the user checking out 
            the token exists within the SLURM user database.
        
        pyflake: if the defined `job_script` is a .py script, it will be flaked 
            for un-used imports before stored internally.

    """

    job_options: SlurmSubmit = SlurmSubmit

    _token_info = {}
    _state = {}

    def __init__(self,
                 name:str, 
                 profile: SlurmCluster,
                 user: Optional[str] = pwd.getpwuid(os.getuid()).pw_name,
                 env_modules: Optional[list] = None,
                 env_extra: Optional[Dict[str, Any]] = None,
                 job_script: Optional[Union[Callable[..., Any], str]] = None,
                 job_script_args: Optional[List[str]] = None,
                 dependencies: Optional[Dict[DependencyType, Union[str, List[str]]]] = None,
                 command: Optional[str] = None, 
                 jwt_lifespan: Optional[int] = 7200,
                 pyflake: Optional[bool] = True,
                 **kwargs
                ):
        
        
        self.name: str = name
        self.user: Optional[str] =user
        self.pyflake: Optional[bool] = pyflake
        self.job_script: Optional[Union[Callable[..., Any], str]] = job_script
        self.command: Optional[str]  = command
        self.dependencies = dependencies 
        
        # if context not set, set context root to callable path
        if not env.CONTEXT_ROOT:
            cpath = Path(sys.argv[0])
            if (cpath.is_file() and
                'site-packages' not in sys.argv[0].split(os.path.sep)):
                env.CONTEXT_ROOT = Path(cpath.resolve()).parent
                if isinstance(self.job_script, str):
                    self.job_script = str(Path(env.CONTEXT_ROOT) / self.job_script)


        # check if path exists and read in - in remote job overload this 
        # attribute and check if path is remote or local
        if isinstance(self.job_script, str):
            self.job_script_args: Optional[List[str]] = job_script_args
            with JobScript(self.job_script, 
                    job_script_args=self.job_script_args, command=command) as code:
                self.script = code.script
                self.code = code

        #self.__context_tree = ContextTree
        # TODO: allow being passed a function
        # else: 
        #    with PyFunction(job_script) as code:
        #        self.script = code.script

        
        self.__lifespan: Optional[int] = jwt_lifespan
        self.token = self.generate_token()
        
        
        # build request url
        self.api_version = profile.api_version
        self.protocol = profile.api_proto
        self.host = profile.api_host
        self.port = profile.api_port
        self.url = f"{self.protocol}://{self.host}:{self.port}/slurm/v{self.api_version}/job/submit"
        
        # unload any loaded versions of python that could conflict
        module('unload', *['python', 'python3', 'anaconda', 'anaconda3'])

        # load requested modules to environment
        self.env_modules: Optional[list] = env_modules
        if env_modules is not None:
            module('load', *self.env_modules)
        
        self.env_extra: Optional[Dict[str, Any]] = env_extra
        self.__set_environment(**kwargs)

        # build request
        self.slurm_header = self.request_header()
        self.request = SlurmModel(job=self.job_options(environment=self.environment, name=self.name, **kwargs),
                                       script=self.script)
        self.jobid = None
        self.monitor_polls = 0
        self.job_monitor = {}

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
    
    def __str__(self):
        
        job_sum = self.request.job.dict()
        job_sum = {k:v for k,v in job_sum.items() if 'environment' not in k}
        job_sum = {k:v for k,v in job_sum.items() if 'name' not in k}
        job_string = ''
        for key, val in job_sum.items():
            job_string += f'\t\t{key}: {val}\n'

        formatted_script = '\n'.join(['\t\t{}'.format(x) for x in self.script.split("\n")])
        # should add if statement to add additional attributes that appear after submitting or begining to monitor
        import textwrap
        return textwrap.dedent(f"""
        🤖 User: {self.user}
        📇 Job Name: {self.name}
        📜 Job Script Language: {self.code.lang}
        🎟️  JWT Token: {self.token}
        🖥️  API Host: {self.host}
        🌐 URL: {self.url}
        🐍 Pyflake: {self.pyflake}
        🕹️  Modules: {self.env_modules}
        🎛️  Extra Env: {self.env_extra}

        📡 Request Summary:
          🛠️ job:
    {job_string}
          📜 script:
    {formatted_script}
        """)

    def __repr__(self):
        return f"{self.name} {self.jobid}"

    def context_tree(self):
        ctx_tree = ContextTree.render()

    def __set_environment(self, **kwargs):

        # parse current environment 
        local_env = dict(os.environ)

        # add user defined env vars to local environmnet
        if self.env_extra is not None:

            # create local copy of extra_env
            udef = self.env_extra.copy()
            
            for key in self.env_extra.keys():
                
                # set to user defined value when not defined in local env
                if local_env.get(key) is None:
                    local_env[key] = udef.pop(key)
                
                # prepend user defined value to local env when defined locally
                else:
                    uval = udef.pop(key)
                    
                    # if var def starts with : then append to local env value
                    if uval.startswith(":"):
                        local_env[key] = f"{local_env[key]}{uval}"
                    
                    # if var def ends with : then prepend to local env value
                    elif uval.endswith(":"):
                        local_env[key] = f"{uval}{local_env[key]}"
                    
                    # else overwrite the local env value
                    else:
                        local_env[key] = uval

        # remove json type variables that don't do well with requests
        local_env = {k: v for k, v in local_env.items() if 'BASH_FUNC' not in k}

        self.environment = local_env

    @property
    def jwt_lifespan(self):
        """
        Ensures that shared token accross multiple jobs
        will have the same value for jwt_ifespan as that of the first
        job submitted (i.e the token should expire at the same time)
        """
        if self._token_info.get('jwt_lifespan') is not None:
            return self._token_info.get('jwt_lifespan')
        else:
            self._token_info.setdefault('jwt_lifespan', self.__lifespan)
            return self.__lifespan

    @property
    def jwt_token_expired(self):
        if self._token_info.get('jwt_start_time') is not None:
            return time.time() - self._token_info.get('jwt_start_time') >= self.jwt_lifespan
        else:
            return False

    
    @property
    def jwt_start_time(self):
        return self._token_info.get('jwt_start_time')
    

    @property
    def jwt_elapsed_time(self):
        if self._token_info.get('jwt_start_time') is None:
            return None
        else:
            return time.time() - self.jwt_start_time

    def submit(self, job_monitor: Optional[bool]=False, delay: Optional[int]=0):
        """
        Submit a simple local script

        Need to check for shebangs #! in script (needed)
        Need to load the right environment modules to run the script
        remote submit should have options to copy local data to remote cluster in working directory for job
        """
        response = requests.post(self.url, data=json.dumps(self.request.dict(exclude_unset=True)), headers=self.slurm_header)
        self.response = json.loads(response.content)
        self.jobid = self.response['job_id']

        if delay > 0: 
            time.sleep(delay)

    def monitor(self, poll_time=5):
        
      
        self.monitor_url =  f"{self.protocol}://{self.host}:{self.port}/slurm/v{self.api_version}/job/{self.jobid}"
        response = requests.get(self.monitor_url, headers=self.request_header())
        self.jwt_elapsed_time = time.time() - self.jwt_start_time
        try: 
            self.job_state = response['job_state']
            self._state[self.name] = {'jobid': self.jobid, 'state': self.job_state}
            if self.job_state == "QUEUED":
                logger.info(f"Job {self.jobid} is currently: {self.job_state}")
                time.sleep(poll_time*2)
                self.monitor()

            if self.job_state == "RUNNING":
                logger.info(f"Job {self.jobid} is currently: {self.job_state}")
                time.sleep(poll_time)
                self.monitor()
            
            if (self.job_state == "COMPLETED" or
                self.job_state == "CANCELLED"):
                logger.info(f"Job {self.jobid} has changed state to: {self.job_state}")
                return self.job_state, self.monitor_polls

            if (self.job_state == "TIMEOUT" or 
                self.job_state == "FAILED"):
                logger.error(f"Job {self.jobid} has changed state to: {self.job_state}")
                return self.job_state, self.monitor_polls
        
        except KeyError:
            logger.error("Job state not found")

            # generate new jwt token if expired
            if self.jwt_token_expired:
                logger.error(f"JWT token has expired ({self.jwt_elapsed_time} >= {self.jwt_lifespan})")
                logger.info("Generating a new token")


            else:
                logger.error("Somethings not right here ... check if job {self.jobid} exists in SLURM DB")
                exit(1)


    def generate_token(self, encoding='utf-8'):
        """
        Generate SLURM JWT token for authenticating request
        """

        if self._token_info.get('jwt_token') is None:
            # generate jwt token        
            process = subprocess.Popen(['scontrol', 'token', f'lifespan={self.__lifespan}'], stdout=PIPE, stderr=PIPE)
            raw, err = process.communicate()
        
            # start token expiry timer
            self._token_info.setdefault('jwt_start_time', time.time())
            
            # set job token attribute
            jwt_token = raw.decode(encoding).rstrip().split('=')[-1]
            logger.info(f"SLURM_JWT={jwt_token}")
            self._token_info.setdefault('jwt_token', jwt_token)
        
        if self.jwt_token_expired:
            self._token_info = {}
            self.generate_token(encoding=encoding)

        return self._token_info.get('jwt_token')

    
    def request_header(self):
        """
        Generate request header with username and JWT token
        """
        return {
                'Content-Type': 'application/json',
                'X-SLURM-USER-NAME': self.user, 
                'X-SLURM-USER-TOKEN': self.token
               }