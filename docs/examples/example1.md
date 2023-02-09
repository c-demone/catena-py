# Example 1 - Using <code>SLURMRESTJob</code> to Submit Job Locally
---
A first example to show how the SLURMRESTJob object can be used

The <code>**kwargs</code> for <code>SLURMRESTJob</code> can be found listed the [SlurmSubmit](../models.md#slurm_submit) schema. This consists of all possible the SLURM SBATCH options, of which only a few are of interest in most cases.

Additionally, `SlurmJob` has external or [extra options](../jobs/slurmrestjob.md#ext_opts). These are options used to specify a given job definition, but that are not SLURM sbatch options.

In this example, a `SlurmJob` object in initialized with the following configuration:

1. `name`: the name of the job once submitted to the SLURM scheduler will be *slurmjobs_example1*
2. `job_script`: path to script to be submitted as a job (when using relative paths upon invoking a `SlurmJob` object, the paths should be relative to the script's path that invokes `SlurmJob`.)
3. `env_extra`: a dictionary, where they keys are the environment variable name to be set and the values are the corresponding values to assign to the associated key/environment variable. There are some caveats that allow appending, prepending of replacing a given environment variable if it already exists within the local environment that are discussed [below](#env_extra)
4. `standard_out`: path to write stdout to file - notice in the example that it is acceptable to use `~` to specify the `$HOME` directory path of the current user
5. `standard_error` path to write stderr to file - again the `~` is used
6. `tasks`: number of tasks for SLURM to run
7. `cpus_per_task`: number of CPUs to assign per task (total CPUs = tasks * cpus_per_task)
8. `memory_per_node`: total memory to request for SLURM per node (default number of nodes requested is 1, unless specified otherwise)
9. `env_modules`: list of strings with the names of environment modules to be loaded when running `job_script` (this is equivalent to executing `module load <module>` for each module before running `job_script`).


In particular this example runs a `Golang` binary, which prints 'Hello World!' unless an environment variable `NAME` is defined in the local environment. 

🛎️ **Important**: a `job_script` without an extension is assumed to be a compiled binary and is run as such. This allows `catena` to extend beyond scripting languages to compiled binaries 

🛎️ **Important**: `catena` attempts to be as language-agnostic as possible when it comes to what can be used for defining a `Job` object such as `SlurmJob`

To set/unset environment variables in a **bash** shell:

<div class="termy">
```console
// To set the NAME environment variable locally
$ export NAME='my name'
// To unset the NAME environment variable locally
$ unset NAME
```
</div>
</br>

## <a name="env_extra_feats"></a> Appending, Prepending and Replacing Local Environment Variables: `env_extra`
The example demonstrates the use of the `env_extra` `kwarg` in `SlurmJob`,  using 'Christopher' as the name. You can change this in the script to your own name. 

There are a couple caveats with how the values in the `env_extra` `dict` are treated, where each keys are the name of the environment variables and the values are the corresponding values.

1. **To prepend** your value to an existing value for a given environment variable **append your value with** `:`
2. **To append** your value to an existing value for a given environment variable **prepend your value with** `:`
3. **To replace** an existing value with your value for a given environment variable **neither prepend or append your value with** `:`

📝**Note**: for (1) and (2) if the variable does not exist in your local environment than it will just set it to that default value.

📝**Note**: <code>rich</code> is a great library for nicely printing things to the console. The inspect method 
is used here to expose what the class looks like and what it contains once defined.

The code for this example is include in the repo at `examples/0_simple_slurm_job/slurm_job1.py` along with example scripts of various languages in `examples/scripts`. 

## Running the Example from the Cloned Repository
*See a Jupyter Notebook code sample for this example [here](../code_samples/example1.ipynb) if you're not interested in runnning it yourself*

📍 Move into the example directory and load <code>anaconda3/2021.05</code> (or your favourite version, as long as python >= 3.6)

<div class="termy">

```console
$ cd examples/0_simple_slurm_job/
$ module load anaconda3/2021.05
```

</div>
</br>

📍 Execute the code

<div class="termy">

```console
// to view job object before submitting a job
$ python3 slurm_job1.py
   
// to view job object before and after submitting a job
$ python3 slurm_job1.py -s
```

</div>

📍 View results of job output

<div class="termy">

```console
// View results of example
$ cat ~/go_hello_world.out
   
```

</div>

📝 **Note**: To run this script and have it submit a job, you should add the -s flag
    e.g: <code>python3 slurm_job1.py -s</code>
