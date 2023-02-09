# Job Manifests
---

Job manifests are YAML files that allows you to organize instructions for submitting any number of jobs  or scripts of various languages to SLURM for scheduling within the cluster. 

![Manifests Process](img/manifests_process.png)


## Structure of a Job Manifest

They are comprised of two sections:

1. **job_options** (*Optional*): Section under which job option blocks can be added. Each of these named configuration sets defines SLURM sbatch options and environment modules that should be loaded for a given job. A single option block can be applied to a single job, or multiple jobs that run different scripts, but have similar requirements. These named configuration sets are referenced using the built-in <code>&</code> and <code>*</code> constructors in YAML.
   
2. **jobs** (*Required*): Section under which jobs to run are defined. 

![Manifest Structure](img/manifest_structure.png)

The most basic job manifest is for a single job, with the optional <code>job_options</code> section excluded:


```yaml
---
jobs:
  - matlab_test:
      job_script: "/path/to/matlab/script/to/run.m"
      job: 
        env_modules:
          - matlab/96
        standard_out: '/path/to/stdout/file.out'
        standard_error: '/path/to/stderr/file.err'
        cpus_per_task: 2
        tasks: 1
        memory_per_node: '2GB'
```

This manifest will submit a job with the name <code>matlab_test</code> to the SLURM scheduler, requesting a single node with 2 cores and 2GB of RAM. The job will run a MATLAB script, which exists at the full absolute path <code>job_script</code>. In this instance a version of MATLAB is required to run the <code>job_script</code> provided and, therefore, under <code>env_modules</code> we add <code>matlab/96</code> to the list of environment modules to be loaded.

Each job follows the general structure:

```yaml
---
jobs:
  - job_name1:
      job_sript: "path to script to be run"
      job:
        ...job options...
  
  - job_name2:
      job_sript: "path to script to be run"
      job:
        ...job options...
```

Any number of jobs can be defined under the <code>jobs</code> section.

```yaml
---
jobs:
  - job_name1:
      job_sript: "path to script to be run"
      job:
        ...job1 options...
  
  - job_name2:
      job_sript: "path to script to be run"
      job:
        ...job2 options...
  ...
...
```

🛎️ **Important**: The configuration properties that may be defined within a job option block are controlled by the [`SlurmSubmit`(models/slurm_job_schemas.md#slurm_submit) schema. 

In addition to SLURM sbatch options, a given job definition is comprised as many so called [Extra Options](jobs/slurmrestjob.md#ext_opts). These are not SLURM options but are also used in initializing a `Job` object to be submitted 
to a SLURM cluster. 

Here are some key points about ***defining job options*** for a job definition:

- [x] Job options can be defined **globally** under `job_options` and referenced within a given job definition using anchors/aliases under the job key 

- [x] They can be defined locally within a given job definition the job key within a given job definition should be reserved for global job options defined under job_options 

- [x] **All job options that can be defined globally can also be defined locally**

- [x] Job options defined locally will take precedence over global job options defined under the job key 

- [x] Useful for having a shared set of job settings across multiple jobs while still being able to define local job settings that differ from job to job.

## Defining Reusable (Global) Job Options: `job_options`
The basic manifest provided for a MATLAB job could also be re-written using the `job_options` section as follows:

```yaml
---
job_options:
  matlab: &matlab
      env_modules:
        - matlab/96
      standard_out: '/path/to/stdout/file.out'
      standard_error: '/path/to/stderr/file.err'
      cpus_per_task: 2
      tasks: 1
      memory_per_node: '2GB'

jobs:
    matlab_test:
    job_script: "/path/to/matlab/script/to/run.m"
    job: *matlab
```
Here we have defined a job option block using an anchor: <code>&matlab</code>. Using anchors provides a means of freely referencing this block elsewhere within your manifest by calling it with the corresponding alias, <code>*matlab</code>, as shown.

With this in mind, consider a case where we'd like to run a series of jobs in either MATLAB or Python. In this instance the <code>job_options</code> section provides a means of better organizing our manifest:

```yaml
---
job_options:

  matlab: &matlab
    env_modules:
      - matlab/96
    standard_out: '/path/to/stdout/file.out'
    standard_error: '/path/to/stderr/file.err'
    cpus_per_task: 2
    tasks: 1
    memory_per_node: '2GB'

  python: &python
    env_modules:
      - anaconda3/2021.05
    standard_out: '/path/to/stdout/file.out'
    standard_error: '/path/to/stderr/file.err'
    cpus_per_task: 2
    tasks: 1
    memory_per_node: '2GB'

jobs:
  
  - matlab_job1:
      job_script: "/path/to/matlab/script/to/run.m"
      job: *matlab
  

  - python_job1:
      job_script: "/path/to/python/script/to/run1.py"
      job: *python

  - python_job2:
      job_script: "/path/to/python/script/to/run2.py"
      job: *python
```

Which is equivalent to

```yaml
---
jobs:
  
  - matlab_job1:
      job_script: "/path/to/matlab/script/to/run.m"
      job:
        env_modules:
          - matlab/96
        standard_out: '/path/to/stdout/file.out'
        standard_error: '/path/to/stderr/file.err'
        cpus_per_task: 2
        tasks: 1
        memory_per_node: '2GB'
  
  - python_job1:
      job_script: "/path/to/python/script/to/run1.py"
      job:
        env_modules:
          - anaconda3/2021.05
        standard_out: '/path/to/stdout/file.out'
        standard_error: '/path/to/stderr/file.err'
        cpus_per_task: 2
        tasks: 1
        memory_per_node: '2GB'
  
  - python_job2:
      job_script: "/path/to/python/script/to/run2.py"
      job:
        env_modules:
          - anaconda3/2021.05
        standard_out: '/path/to/stdout/file.out'
        standard_error: '/path/to/stderr/file.err'
        cpus_per_task: 2
        tasks: 1
        memory_per_node: '2GB'
```

Cleary, when the number of jobs and options begins to grow this could become more cumbersome to read. 

- [x] The following is an [example](examples/example2a.md) of a simple job manifest


## <a name="include_constructor"></a>Using the <code>!include</code> Constructor
The <code>!include</code> constructor allows you to *include* options or blocks from other external YML files, given the path. For instance, given three YAML files in the same directory:

  1. ***manifest.yml***: the main manifest 
  2. ***job_opts1.yml***: manifest containing global job options
  3. ***jobs.yml***: manifest containing job definitions

![Include constructor](img/manifests_include.png)

The `!include` constructor can be used for defining either `job_options` or `jobs` or both. For example given two YML files in the same directory, *manifest.yaml* and *jobs.yaml*:
  
*manifest.yaml*
```yaml
---
job_options:
  - matlab: &matlab
      env_modules:
        - matlab/96
      standard_out: '~/man_matlab.out'
      standard_error: '~/man_matlab.err'
      cpus_per_task: 2
      tasks: 1
      memory_per_node: '2GB'

  python: &python
    env_modules:
      - anaconda3/2021.05
    standard_out: '~/man_python.out'
    standard_error: '~/man_python.err'
    cpus_per_task: 2
    tasks: 1
    memory_per_node: '2GB'

jobs: 
  - !include jobs.yaml
```
  
*jobs.yaml*
```yaml
---
jobs:
  - matlab_job1:
     job_script: "/path/to/matlab/script/to/run.m"
     job: *matlab

  - python_job1:
     job_script: "/path/to/python/script/to/run1.py"
     job: *python

  - python_job2:
     job_script: "/path/to/python/script/to/run2.py"
     job: *python
```
This would be equivalent to the explicit manifest previously shown. 

- [x] The following [example](examples/example2b.md) looks at this exact type of application.

🛎️ **Important**: Any number of include statements can be listed for referencing `job_options` and/or `jobs` from external YAML files.  For instance, the Python and MATLAB job definitions were split into two files `matlab_jobs.yaml` and `python_jobs.yaml`. Then, they could be included like this:

```yaml
jobs: 
  - !include matlab_jobs.yaml
  - !include python_jobs.yaml
```

🛎️ **Important**: The `!include` constructor and global `job_options` of a manifest can be used separately or combined to better organize more complex workloads. 

🛎️ **Important**: When global `job_options` are included from external YML files and the global options are tagged with anchors(&), these options can be referenced by there corresponding alias (*). For instance, given the following 2 external YML files and a main manifest:

One external YML files for defining global job options for matlab jobs:

*matlab_opts.yml*
```yaml
---
job_options:
  - matlab: &matlab
      env_modules:
        - matlab/96
      standard_out: '~/man_matlab.out'
      standard_error: '~/man_matlab.err'
      cpus_per_task: 2
      tasks: 1
      memory_per_node: '2GB'
```

Another listing job definitions that alias the `&matlab` anchor
*matlab_jobs.yml*
```yaml
---
jobs:
  - matlab_job1:
      job_script: "/path/to/matlab/script/to/run.m"
      job: *matlab
```

Then, using the `!include` constructor, the main manifest would be:

*manifest.yml*
```yaml
---
job_options:
  - !include matlab_opts.yml

jobs:
  - !include matlab_jobs.yml
```

Or without using the `!include` constructor, the following main manifest would be valid as well:

*manifest.yml*
```yaml
---
job_options:
  - !include matlab_opts.yml

jobs:
  - matlab_job1:
      job_script: "/path/to/matlab/script/to/run.m"
      job: *matlab
```

##  <a name="manifests_bp"></a>Job Manifests Best Practices
Using the `!include` constructor complex manifests can be organized into multiple YML files. For advanced job manifests involving multiple YAML files, it is good practice to keep things organized and make your manifests easy to navigate. Here is a sample manifest directory.

![Best Practices](img/manifests_bp_all.png)

📝**Note**: Any number of directories can be created and referenced within the ***main manifest root directory*** (i.e the directory container the main manifest to be run).

- [x] The following [example](examples/example3.md) demonstrates how this setup can be used in practice. It also serves to demonstrate how relatives paths can be used to define 
`job_options` that correspond to paths, which is the subject of the following section.


## Understanding the Context in Which the Manifest is Run
So far in the toy examples shown, not much attention has been given to the path definitions within job manifests and how they are resolved. In particular, it is generally useful to
use relative paths to clean up a manifest and reduce the verbosity. 

🛎️ **Important**: When definining paths within any manifest, **all paths should be taken relative to the main manifest root directory**:

![Best Practices Dir](img/manifests_bp.png)

In addition to be able to define relative paths, the `~` expression is also valid and is expanded to the full absolute path of the home directory for the user calling  `SlurmJob` or running a manifest.
Ultimately, all paths defined within a manifest or `SlurmJob` are expanded to there absolute form.

📝**Note**: expansion of paths defined within a given job definition (including any job options) is performed when validating the inputs to `SlurmJob` (i.e, using Pydantic validators in both the
[`SlurmSubmit`](models/slurm_job_schemas.md#slurm_submt) and the [`JobOptions`](models/job_manifests.md#job_opts_manifest) schemas)


# Submitting a Manifest
Currently, the `Manifest` object can be invoked by calling the `catena` module directly and providing the path to a manifest to be run. 

<div class="termy">

```console
$ python3 -m catena /path/to/my/manifest.yaml

💻 Submitted job: 300205
💻 Submitted job: 300206
💻 Submitted job: 300207
💻 Submitted job: 300208
```

</div>

📝 **Note**: Currently not packaged.
