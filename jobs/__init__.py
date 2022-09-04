from typing import Optional, List, Any
import asyncio
from concurrent.futures import ProcessPoolExecutor
from rich.columns import Columns
from rich.panel import Panel
from rich.console import Console
import time
from slurmjobs.lib.monitor import Monitor
import os


class Jobs:
    """
    Generic class for storing multiple `Job` instances (e.g SLURMRESTJob or other)
    """

    def __init__(self, jobs: Optional[List] = []):
        
        self.jobs = jobs
        self.queue = asyncio.Queue()
        self.executor = ProcessPoolExecutor(max_workers=4)
        self.loop = asyncio.get_event_loop()
        self.submitted = False
    
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
    
    async def submit(self, delay:Optional[int]=3):

        for job in self.jobs:

            await self.loop.run_in_executor(None, job.submit(delay=delay))

        self.submitted = True
    
    def monitor(self):
        monitor = Monitor(jobs=self.jobs)
        monitor.start()