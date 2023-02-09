# <a name="slurmrestjob"></a>`SlurmJob`
---

::: catena.jobs.slurm.SlurmJob

#### New Attributes After Submitting a SlurmJob

`self.response (dict)`
: raw response from SLURM REST API after invoking <code>POST job/submit</code>;

`self.jobid (str)`
: SLURM job id for the instance of <code>SLURMRESTJob</code>;
   
#### New Attributes After Starting Monitoring of a SLURMRESTJob

`self.monitor_url (str)`
: dynamically constructed API URL based on <code>api_version, protocol, host, port</code> attributes for <code>GET job/{job_id}</code>;

`self.jwt_elapsed_time (float)`
: amount of time in seconds that have elapsed since JWT token was checked out - triggers <code>generate_token</code> when JWT token is expired;\

`self.job_state (str)`
: the jobs current state - this attribute is updated everytime the job state is polled *(cf.[SLURM Job States](https://curc.readthedocs.io/en/latest/running-jobs/squeue-status-codes.html))*;


## <a name="ext_opts"></a>Extra Options

Extra options are options that are not SLURM sbatch options, but are required for defining a `Job` instance. These
include:

1. `env_modules`
2. `job_script`
3. `env_extra`
4. `job_script_args`
5. `command`

📝 **Note**: The definition of each of these can be found [above](#slurmrestjob)

📝 **Note**: How to [append, prepend and replace](../examples/example1.md#env_extra_feats)
