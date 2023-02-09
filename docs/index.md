<p align="center">
  <img src='img/catena-logo.png' width=500px height=275px/>
</p>


---
**<code>catena</code> a Python Utility for Submitting Work to a SLURM Cluster**
---
<code>catena</code> is a Python library for interacting with SLURM through the REST API. In particular,  the library is focused on  the submission of jobs to a SLURM cluster, either locally or remotely, but can be extended to other schedulers with a suitable API.

📝 **Note**: Currently only works when running locally on a SLURM HPC


---
📋 **Key Features**
---

- [x] Provides 'job' classes that allow for work to be orchestrated through SLURM, programatically in Python

- [x] Defines schemas with sensible defaults and validators for SLURM /job/submit request

- [x] Affords end-users the ability to orchestrate multiple jobs in various programming languages using *Job Manifests*

- [ ] Allows building and running pipelines of inter-dependent jobs (DAGs) of various programing languages to be run on a SLURM HPC using *Job Pipelines*

- [] Provides ability to share and cache results of jobs between almost any programming language

📝 **Note**: This project is still under development.

---
**Quickstart**
--
Clone the repository and try out some examples

📍 Move into the repo and load <code>anaconda3/2021.05</code> (or your favourite version, as long as python >= 3.6)

<div class="termy">

```console
$ cd catena/examples
$ module load anaconda3/2021.05
```

</div>


📍 Install all requirements for catena

<div class="termy">

```console
$ pip3 install --user -r requirements.txt
---> 100%
```
</div>

## TODO
- [x] Local job submission single script any language programatically in Python
- [x] Local submission of many job sripts of various languages using *Job Manifests*
- [ ] Unit test all components involved in above
- [ ] Local submission of many interdependent job scripts represented as a DAG using *Job Pipelines*
- [ ] Build out custom loggers using loguru (e.g. job monitor, verbose vs. silent/to file)
- [ ] Unit test all components involved in above
- [ ] Setup GitHub actions for CI/CD
- [ ] Extend all of the above to remote job execution: will require ability to mount remote files possibly using a custom variation on squashfs mixed with gRPC.