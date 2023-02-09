# Example 3 - Best Practices for Complex Manifests
---
The following example demonstrates the suggested setup when dealing with job manifests that span many YML files. This is discussed in greater detail [here](../manifests.md#manifests_bp) - a similar directory structure is used as describe. One addition is made, by including an 'output' directory in the manifest root directory. 

- [x] any number of sub-directories can be included and referenced within the main manifest root directory
- [x] all relative paths defined within all YML files will be taken relative to the main manifest root directory


The main manifest root in this example can be found in `examples/2_job_manifests_bp/complextest/`. Here you will find 4 directories.

1. **jobs**: contains YML files with `job` definitions that are referenced in the main manifest using the `!include` constructor
2. **opts**: contains YML files with global `job_options`, also reference in the main manifest using the `!include` constructor
3. **scripts**: contains scripts of various languages (particularly Python and R for this example)
4. **output**: directory used to store stdout and stderr files from SLURM jobs

The main job manifest is also found in this directory and is named `complex-manifest.yaml` after its purpose: testing various versions of R and Python with a new version of the optimization library [KNITRO](https://www.artelys.com/docs/knitro/)
   
Let's take a look at each of these here:

*complex-manifest.yaml*
```yaml
---
job_options:
  - complex_test: &job_opts
      cpus_per_task: 2
      tasks: 1
      memory_per_node: '2GB'
```

The included global `job_options` are taken from the following:

*opts/job_opts.yaml*
```yaml
---
job_options:
  - knitrotest: &knitrotest
      cpus_per_task: 2
      tasks: 1
      memory_per_node: '2GB'
```

And the included `jobs` are taken from the following:

*jobs/python_jobs.yml*
```yaml
---
jobs:
  - python_test1:
      job_script: "scripts/exampleConic1.py"
      standard_out: 'output/complex-test/python3.10.7_test.out'
      standard_error: 'output/complex-test/python3.10.7_test.err'
      env_modules:
        - python/3.10.7
      job: *job_opts
  
  - python_test2:
      job_script: "scripts/exampleConic1.py"
      standard_out: 'output/complex-test/python3.8.14_test.out'
      standard_error: 'output/complex-test/python3.8.14.err'
      env_modules:
        - python3/3.8.14
      job: *job_opts
```

*jobs/r_jobs.yml*
```yaml
---
jobs:
  - r_test1:
      job_script: "scripts/rosenbrock.R"
      standard_out: 'output/r/r421_test.out'
      standard_error: 'output/r/r421_test.err'
      env_modules:
        - R/4.2.1
      job: *job_opts
```

## Running the Example from the Cloned Repository
*See a Jupyter Notebook code sample for this example [here](../code_samples/example3.ipynb) if you're not interested in runnning it yourself*

📍 Move into the example directory and load <code>anaconda3/2021.05</code> (or your favourite version, as long as python >= 3.6)

<div class="termy">

```console
$ cd examples/2_job_manifests_bp/
$ module load anaconda3/2021.05
```

</div>
</br>

📍 Execute the code

<div class="termy">

```console
// to view job summaries before submitting a job
$ python3 0_complex_manifest.py
   
// to submit jobs
$ python3 0_complex_manifest.py -s
```

</div>