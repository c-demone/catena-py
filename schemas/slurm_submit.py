from pydantic import BaseModel, Field, validator
from typing import Optional, Union
from pathlib import Path

from . import ExtendedBaseModel
import slurmjobs.lib.env as env 


class SLURMSubmit(ExtendedBaseModel):
    """
    SLURM sbatch options: see [SLURM documentation](https://slurm.schedmd.com/sbatch.html)
    for more details. 
      
    Attributes:
        name: SLURM job name
        
        delay_boot: do not reboot nodes in order to satisfied this job's feature 
            specification if the job has been eligible to run for less than this time period,
            **defaults to 0** (suggested to leave as default)

        dependency: defer the start of this job until the specified dependencies have been satisfied completed.
            All dependencies must be satisfied if the ','
            separator is used. Any dependency may be satisfied if the "?" separator is used, **defaults to None**

        distribution: specify alternate distribution methods for remote processes. In sbatch, this only sets 
            environment variables that will be used by subsequent srun requests, **defaults to 'arbitrary'**
        
        environment: map of systems path to be set within the users environment when running the SLURM job, **defaults to None**

        exclusive: The job allocation can not share nodes with other running jobs (or just other users with the '=user' option 
            or with the '=mcs' option), **defaults to 'user'**

        get_user_environment: this option will tell sbatch to retrieve the login environment variables for the user specified in the 
            <code>--uid</code> option, **defaults to None**

        gres: specifies a comma delimited list of generic consumable resources, **defaults to None**

        gres_flags: specify generic and resource task binding options (<code>disable-binding/enforce-bindings</code>), **defaults to 'disable-binding'**

        gpu_binding: bind tasks to specific GPUs. By default every spawned task can access every GPU allocated to the step, **defaults to 'closest'**

        gpu_frequency: request that GPUs allocated to the job are configured with specific frequency values. This option can be used to independently configure 
            the GPU and its memory frequencies, **defaults to 'medium'**
        
        gpus: specify the total number of gpus required for the job '<type>:number', **defaults to None**

        gpus_per_node: specify the number of GPUs required for the job on each node included in the job's resource allocation, **defaults to None**

        gpus_per_socket: specify the number of GPUs required for the job on each socket included in the job's resource allocation. An optional GPU 
            type specification can be supplied, **defaults to None**

        gpus_per_task: specify the number of GPUs required for the job on each task to be spawned in the job's resource allocation. An optional GPU type 
            specification can be supplied
        
        hold: specify the job is to be submitted in a held state (priority of zero). A held job can now be released using scontrol to reset 
            its priority (e.g. 'scontrol release <job_id>'), **defaults to false**
        
        licenses: specification of licenses (or other resources available on all nodes of the cluster) which must be allocated to this job.
            License names can be followed by a colon and count (the default count is one). Multiple license names should be comma separated 
            (e.g. '--licenses=foo:4,bar')
        
        mail_type: notify user by email when certain event types occur, **defaults to 'NONE'** (see SLURM documentation for full list of options)

        mail_user: user to receive e-mail notification of state changes defined by <code>--mail-type</code>, **defaylts as None**

        memory_binding: bind tasks to memory. Used only when the task/affinity plugin is enabled and the NUMA memory functions are available, **defaults to None**.

        memory_per_cpu: minimum memory required per allocated CPU (default units are MB, different units can be specified using the suffix [K|M|G|T]), **defaults to 0**

        memory_per_gpu: minimum memory required per allocated GPU (default units are megabytes, different units can be specified using the suffix [K|M|G|T]),
            **defaults to 0**

        memory_per_node: specify the real memory required per node (default units are megabytes, different units can be specified using the suffix [K|M|G|T]),
            **defaults to 0**

        cpus_per_task: advise the SLURM controller that ensuing job steps will require ncpus number of processors per task. Without this option, 
            the controller will just try to allocate one processor per task, **defaults to 0**

        minimum_cpus_per_node: specify a minimum number of logical cpus/processors per node, **defaults to 0**
       
        minimum_nodes: if a range of node counts is given, prefer the smaller count, **defaults to 'true'**

        nice: run the job with an adjusted scheduling priority within Slurm. With no adjustment value the scheduling priority 
            is decreased by 100. A negative nice value increases the priority, otherwise decreases it, **defaults to None**
        
        no_kill: do not automatically terminate a job if one of the nodes it has been allocated fails. 
            The user will assume the responsibilities for fault-tolerance should a node fail. When there is a node failure, 
            any active job steps (usually MPI jobs) on that node will almost certainly suffer a fatal error, but with 
            <code>--no-kill</code>, the job allocation will not be revoked so the user may launch new job steps on the remaining 
            nodes in their allocation, **defaults to 'off'**

        nodes: Request that a minimum of minnodes nodes be allocated to this job. A maximum node count may also be specified with maxnodes. 
            If only one number is specified, this is used as both the minimum and maximum node count. The partition's node limits supersede 
            those of the job. If a job's node limits are outside of the range permitted for its associated partition, the job will be left 
            in a PENDING state, **defaults to 1**
        
        open_mode: (append|truncate) open the output and error files using append or truncate mode as specified. The default value is specified by the system 
            configuration parameter JobFileAppend, **defaults to 'append'**

        partition: request a specific partition for the resource allocation, **defaults to 'normal'**

        qos: request a quality of service for the job, **defaults to 'user'**
 
        requeue: specifies that the batch job should be eligible for requeuing, **defaults to 'true'**

        reservation: allocate resources for the job from the named reservation, **defaults to None**

        sockets_per_node: restrict node selection to nodes with at least the specified number of socket, **defaults to 0**

        spread_job: Spread the job allocation over as many nodes as possible and attempt to evenly distribute tasks across 
            the allocated nodes (this option disables the topology/tree plugin), **defaults to 'true'**

        standard_error: instruct SLURM to connect the batch script's standard error directly to the file name at the specified path,
            **defaults to None**

        standard_in: instruct Slurm to connect the batch script's standard input directly to the file name at the specified path,
            **defaults to None**

        standard_out: instruct Slurm to connect the batch script's standard output directly to the file name at the specified path,
            **defaults to None**

        tasks: sbatch does not launch tasks, it requests an allocation of resources and submits a batch script. This option advises the 
            SLURM controller that job steps run within the allocation will launch a maximum of number tasks and to provide for sufficient resources, 
            **defaults to 1 task per node, but note that the <code>--cpus-per-task</code> option will change this default.

        tasks_per_core: request the maximum ntasks be invoked on each core (meant to be used with the <code>--ntasks</code> option),
            **defaults to 0**

        tasks_per_node: r that ntasks be invoked on each node (if used with the --ntasks option, the <code>--ntasks</code> option will take precedence 
            and the <code>--ntasks-per-node</code> will be treated as a maximum count of tasks per node), **defaults to 0**

        tasks_per_socket: request the maximum ntasks be invoked on each socket (meant to be used with the <code>--ntasks</code> option),
            **defaults to 0**

        threads_per_core: restrict node selection to nodes with at least the specified number of threads per core. In task layout, 
            use the specified maximum number of threads per core, **defaults to 0**

        time_limit: set a limit on the total run time of the job allocation, **defaults to None**

        wait_all_nodes: (0|1) controls when the execution of the command begins, **defaults to 0** (the job will begin execution as soon as 
        the allocation is made)

        wckey: specify wckey to be used with job, **defaults to None**

        cores_per_socket: restrict node selection to nodes with at least the specified number of cores per socket, **defaults to None**

        core_specifications: count of specialized cores per node reserved by the job for system operations and not used by the application,
            **defaults to None**
    """
    name: str
    delay_boot: Optional[int] = 0   # leave set to 0
    dependency: Optional[str] = None   
    distribution: Optional[str] = 'arbitrary'
    environment: Optional[dict] = None
    exclusive:  Optional[str] = "user"
    get_user_environment: Optional[str] = None
    gres: Optional[str] = None
    gres_flags: Optional[str] = "disable-binding"
    gpu_binding: Optional[str] = "closest"
    gpu_frequency: Optional[str] = "medium"
    gpus: Optional[str] = None
    gpus_per_node: Optional[str] = None 
    gpus_per_socket: Optional[str] = None
    gpus_per_task: Optional[str] = None
    hold: Optional[str] = 'false'
    licenses: Optional[str] = None 
    mail_type: Optional[str] = "NONE"
    mail_user: Optional[str] = None
    memory_binding: Optional[str] = "none"
    memory_per_cpu: Optional[str] = 0
    memory_per_gpu: Optional[str] = 0
    memory_per_node: Optional[str] = 0
    cpus_per_task: Optional[int] = 0
    minimum_cpus_per_node: Optional[str] = 0
    minimum_nodes: Optional[str] = 'true'
    nice: Optional[str] = None
    no_kill: Optional[str] = 'off'
    nodes: Optional[int] = 1
    open_mode: Optional[str] = 'append'
    partition: Optional[str] = 'normal'
    qos: Optional[str] = 'user' 
    requeue: Optional[str] = 'true'
    reservation: Optional[str] = None
    sockets_per_node: Optional[int] = 0
    spread_job: Optional[str] = 'true'
    standard_error: Optional[str] = None
    standard_in: Optional[str] = None
    standard_out: Optional[str] = None
    tasks: Optional[int] = 1
    tasks_per_core: Optional[int] = 0
    tasks_per_node: Optional[int] = 0
    tasks_per_socket: Optional[int] = 0
    threads_per_core: Optional[int] = 0
    time_limit: Optional[Union[int, str]]  = None
    wait_all_nodes: Optional[str] = 0
    wckey: Optional[str] = None
    cores_per_socket: Optional[int] = None
    core_specifications: Optional[int] = None
    
    @validator('standard_error', 'standard_out', 'standard_in')
    def expand_home_shortcut(cls, v):
        if v is not None:
            if str(v.startswith('~')):
                ppath = Path(v)
                return str(ppath.expanduser())
            else:
                return v
        else:
            return v
    
    @validator('standard_error', 'standard_out', 'standard_in')
    def check_abs_paths(cls, v):
        if v is not None:
            if not Path(v).is_absolute():
                return str(Path(env.CONTEXT_ROOT) / v)
            else:
                return v
        else:
            return None


class SLURMJob(BaseModel):
    """
    General SLURM job schema including job options and the job script path, used for
    submitting a job through the REST API: <code>POST job/{jobid}</code> 
      
    Attributes:
        script: full absolute path to script to be submitted as a job to the SLURM cluster
        
        job: SLURM sbatch options for the associated job
    """
    script: str
    job: SLURMSubmit = Field(...)