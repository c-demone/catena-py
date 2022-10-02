from typing import Optional, List, Any, Union
import asyncio
from concurrent.futures import ProcessPoolExecutor
from rich.columns import Columns
from rich.panel import Panel
from rich.console import Console
import time
import networkx as nx
from pathlib import Path
import sys
import os

from .slurm import SlurmJob
import catena.lib.env as env
from ..lib.yaml_loader import Loader, safe_loader
from ..models import JobManifest, CatenaConfig
# include DAGS, run_manifest etc. # jobs module should contain dask-esque break down of slumr job tasks.



class Jobs:
    """
    Generic class for storing multiple `Job` instances (e.g SlurmJob or other)
    """

    def __init__(self, jobs: Optional[Union[List[SlurmJob], List[Any]]] = []):
        
        self.jobs = jobs
        self.queue = asyncio.Queue()
        self.executor = ProcessPoolExecutor(max_workers=4)
        self.loop = asyncio.get_event_loop()
        self.submitted = False

        self.dag = TaskDAG(self.jobs)
    
    def append(self, item: Any):
        self.jobs.append(item)
    
    def pop(self, index:int):
        self.jobs.pop(index)

    def __getitem__(self, index:int):
        return self.jobs[index]
    
    def __len__(self):
        return len(self.jobs)
    
    def __str__(self):
        console = Console()
        jobs = [Panel(self.get_job_content(job), expand=True) for job in self.jobs]
        console.print(Columns(jobs))
        return ''

    def brief(self):
        jobs = [Panel(self.get_job_content(job), expand=True) for job in self.jobs]
        return Columns(jobs)

    
    @property
    def job_map(self):
        """
        Provides hash-map of {'jobid': JobInstance}
        """
        _map = {}
        for job in self.jobs:
            if hasattr(job, 'jobid'):
                _map[job.get('jobid')] = job

        return _map 


    def get_job_content(self, job):
        job_sum = job.request.job.dict()
        job_sum = {k:v for k,v in job_sum.items() if 'environment' not in k}
        job_sum = {k:v for k,v in job_sum.items() if 'name' not in k}
        job_string = ''
        for key, val in job_sum.items():
            job_string += f'\t\t{key}: {val}\n'

        jobid = "[bold red]UNSUBMITTED[/bold red]" if job.jobid is None else f"[green]{job.jobid}[/green]"
        import textwrap
        return textwrap.dedent(f"""
        🤖 User: {job.user}
        🎆 Job ID: {jobid}
        📇 Job Name: {job.name}
        📜 Job Script Language: {job.code.lang}
        🎟️  JWT Token: {job.token}
        ⏰ JWT Start Time: {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(job.jwt_start_time))}
        🖥️  JWT Token Expired: {job.jwt_token_expired}
        📜 Job Script Path: {job.job_script}
        """)
    
    #def sort(self):
    #    """
    #    Topologically sort jobs in DAG
    #    ""
    

    async def submit(self, delay:Optional[int]=3):
        # TODO: make sure this works.

        for job in self.jobs:

            await self.loop.run_in_executor(None, job.submit(delay=delay))

        self.submitted = True
    
    #def monitor(self):
    #    monitor = Monitor(jobs=self.jobs)
    #    monitor.start()

class Manifest:

    def __init__(self, manifest: str, _submit:Optional[bool]=True):
        
        self.jobs = Jobs()
        self.manifest = manifest
        self.submitted = False
        self._submit = _submit


    def __enter__(self):
        """
        Set context relative to directory in which indicated file
        exits.
        """
        ppath = Path(self.manifest)
        env.MAIN_MANIFEST = ppath.name
        if not ppath.is_absolute():
            cpath = Path(sys.argv[0])

            # if being invoke from python script and not notebook
            if (Path(cpath.resolve()).is_file() and 
            'site-packages' not in sys.argv[0].split(os.path.sep)):
                
                self.manifest = Path(Path(cpath.resolve()).parent) / self.manifest
                ppath = Path(self.manifest)
            env.CONTEXT_ROOT = Path(ppath.resolve()).parent
            self.manifest = Path(env.CONTEXT_ROOT) / env.MAIN_MANIFEST

        else:
            env.CONTEXT_ROOT = ppath.parent

        self.parse_manifest()

    def __exit__(self, exc_type,exc_value, exc_traceback):
        env.CONTEXT_ROOT = None
        env.MAIN_MANIFEST = None


    def open(self):
        """
        Open manifest context
        """
        self.__enter__()

        if self._submit:
            self.submit()
        
        return self
    

    def close(self):
        """
        Close manifest context
        """
        self.__exit__()

    
    def parse_manifest(self):
        # read manifest

        with open(self.manifest, 'r') as f:
            data = safe_loader(f, Loader=Loader)

        conf = CatenaConfig.read(data.get('catena_config'))
        cp = conf.get_profile(data.get('cluster_profile'))

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
            #TODO: Add cluster_profile to get backend and determine job type
            # to accomodate more than slurm in the future.
            if cp.backend == 'slurm':
                if data.get('catena_config') is None:
                    _profile = data.get('cluster_profile')
                else:
                    _profile = f"{data.get('cluster_profile')}@{data.get('catena_config')}"
                with SlurmJob(profile=data.get('cluster_profile'),
                              env_modules=jobdef.env_modules, 
                              job_script=jobdef.job_script,
                              job_script_args=jobdef.job_script_args,
                              command=jobdef.command,
                              env_extra=jobdef.env_extra, 
                              dependencies=jobdef.dependencies,
                              **jobdef.job.dict(exclude_none=True)) as job:
                    self.jobs.append(job)       
            

    def submit(self):
        """Submit job manifest to cluster"""
        
        # CREATE DAG HERE and order list using a topological sort
        # on DAG before submitting jobs so that they are in right order
        
        self.jobs.submit()
        self.submitted = True
        return self.jobs


class TaskDAG(nx.DiGraph):

    def __init__(self, jobs: Union[List[SlurmJob], List[Any]]):

        super().__init__()
        edges = []
        self.jobs = jobs

        for job in self.jobs:
            # G.node[job.name][attrs] = job object
            # G.node.get(job.name).get(job).jobid <- will update
            # once the job is submitted.
            # so topo sort nodes, submit jobs in order
            
            self.add_node(job.name, job=job)
            if job.dependencies is not None: 
                for dep_type in job.dependencies:
                    tmpstr = ''
                    for dep in job.dependencies.get(dep_type):
                        depjob = self.get_job(dep)
                        edges.append([depjob, job, dep_type])
                        job.depmap[dep_type].append(depjob)

        # label edge[:-1] by dependency type[-1]
        self.edge_labels = {tuple(e[:-1]): e[-1] for e in edges}
        self.add_edges_from([e[:-1] for e in edges])


    def get_job(self, job_name:str):
        """
        Return job object by job name
        """
        return next((j for j in self.jobs if j.name == job_name), None)


