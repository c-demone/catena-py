# Example 2b - Using the !include Constructor to Define Jobs
---

This example introduces the concept of [!include](../manifests.md#include_const) constructor that can be used to organize more complex job manifiests. Specifically, we will see how we can include jobs in a manifest from any number of external YAML files.

The manifests used in this example can be found in `examples/1_job_manifests/sample_manifests/include_example`. Here you will find 3 YAML files:

1. advanced_manifest.yml
2. julia_jobs.yml
3. python_jobs.yml
   
Let's take a look at each of these here:

*advance_manifest.yml*
```yaml
---
version: 1.0
cluster_profile: my_slurm_cluster1
job_options:
  - matlab: &julia
      env_modules:
        - julia/1.7.2
      cpus_per_task: 2
      tasks: 1
      memory_per_node: '2GB'

  - python: &python
      env_modules:
        - python/3.10.7
      cpus_per_task: 2
      tasks: 1
      memory_per_node: '2GB'

jobs: 
  - !include julia_jobs.yml
  - !include python_jobs.yml
```
This is the primary *manifest* that would be executed. The next two YAML files provide lists of job definitions. The first comprised entirely of MATLAB jobs while the second defines a list of Python jobs. This is one way in which the `!include` constructor can be used to 
organize a manifest better, and avoid having a single monstrous manifest for more complex workloads.

*julia_jobs.yml*
```yaml
---
jobs:
  - julia_test1:
      job_script: "../../../scripts/test.jl"
      standard_out: '~/julia_test1.out'
      standard_error: '~/julia_test1.err'
      job: *julia
  
  - julia_test2:
      job_script: "../../../scripts/test.jl"
      standard_out: '~/julia_test2.out'
      standard_error: '~/julia_test2.err'
      job: *julia
```

*python_jobs.yml*
```yaml
---
jobs:
  - python_test1:
      job_script: "../../../scripts/test.py"
      standard_out: '~/python_test1.out'
      standard_error: '~/python_test1.err'   
      job: *python
  
  - python_test2:
      job_script: "../../../scripts/test.py"
      standard_out: '~/python_test2.out'
      standard_error: '~/python_test2.err'
      job: *python
```

Notice that  in both `julia_jobs.yml` and `python_jobs.yml` there are two SLURM configuration properties that are defined locally within the job definition block outside of the `job` section or not globally using the `*python` alias or `*julia` alias. This is useful when you'd like to have a series of jobs with similar resources requirements that can be defined through the use of *aliases* such as `*python` but also have some SLURM configuration options that you'd like to be different between each job definition. This is most apparent for `standard_out` and `standard_error` where having the same value accross jobs would result in the stdout and stderr files produced by one job being overwritten by the next.

These are termed *local* job definitions, and they can be used for any SLURM configuration option found within the [SlurmSubmit](../models/slurm_job_schemas.md#slurm_submit) schema. The exceptions to this include:

1. `name`: the job name is a required parameter that must be defined as the key or head of the node of the local job def (e.g: `- python_test2:` as shown in *python_jobs.yaml*)
   
2. `env_modules`: this parameter is not a SLURM configuration property but rather a "wrapper" for the `environment` property. It is setup, however, such that you are able to set this at the *local* or *global* level, since this may also be useful in some instance (e.g testing your code wih different versions of the language)

## Running the Example from the Cloned Repository
*See a Jupyter Notebook code sample for this example [here](../code_samples/example2b.ipynb) if you're not interested in runnning it yourself*

📍 Move into examples directory and load <code>anaconda3/2021.05</code> (or your favourite version, as long as python >= 3.6)

<div class="termy">

```console
$ cd slurmjobs/examples/1_job_manifests
$ module load anaconda3/2021.05
```

</div>
</br>

📍 Execute the code

<div class="termy">

```console
// to view job object before submitting a job
$ python3 1_include_example.py
   
// to view job object before and after submitting a job
$ python3 1_include_example.py -s
```