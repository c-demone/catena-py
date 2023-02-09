# Example 2a - Using Job Manifests to Organize Workloads
---

This example introduces the concept of [Job Manifests](../manifests.md), which are YAML files that can be used to specify the configuration of multiple SLURM jobs in an easily readible and re-usable way.

As an introduction, a basic manifest is provided in `examples/1_job_manifests/sample_manifests/basic_manifest.yaml`

*basic_manifest.yaml*
```yaml
---
version: 1.0
cluster_profile: 'my_slurm_cluster1'
job_options:

  - python: &python
      env_modules:
        - python/3.10.7
      standard_out: '~/man_python.out'
      standard_error: '~/man_python.err'
      cpus_per_task: 2
      tasks: 1
      memory_per_node: '2GB'

  - R: &r
      env_modules:
        - R/4.2.1
      standard_out: '~/man_python.out'
      standard_error: '~/man_python.err'
      cpus_per_task: 2
      tasks: 1
      memory_per_node: '2GB'

  - julia: &julia
      env_modules:
        - julia/1.8.1
      standard_out: '~/man_julia.out'
      standard_error: '~/man_julia.err'
      cpus_per_task: 2
      tasks: 1
      memory_per_node: '2GB'   


jobs:
  
  - python_test:
      job_script: "../../scripts/test.py"
      job: *python
  
  - r_test:
      job_script: "../../scripts/test.r"
      job: *r
  
  - julia_test:
      job_script: "../../scripts/test.jl"
      job: *julia 
```
This example will submit four jobs of four different languages, MATLAB, Python, R, and Julia. Theoretically, SLURMRESTJob should work for almost any language job script, including compiled binaries.

## Running the Example from the Cloned Repository
*See a Jupyter Notebook code sample for this example [here](../code_samples/example2a.ipynb) if you're not interested in runnning it yourself*

📍 Move into examples directory and load <code>anaconda3/2021.05</code> (or your favourite version, as long as python >= 3.6)

<div class="termy">

```console
$ cd slurmjobs/examples/1_job_manifests
$ module load anaconda3/2021.05
```

</div>

📍 Execute the code

<div class="termy">

```console
// to view job object before submitting a job
$ python3 0_basic_manifest.py
   
// to view job object before and after submitting a job
$ python3 0_basic_manifest.py -s
```