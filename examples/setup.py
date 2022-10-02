from  pathlib import Path

sample_conf='''---
version: 1.0
clusters:
  my_slurm_cluster1:
    backend: slurm
    api_host: skynet-master1
  my_slurm_cluster2:
    backend: slurm
    api_host: terminator-master1'''

cc_path = Path(str(Path.home() / '.catena'))
cc_path.mkdir(parents=True, exist_ok=True)

with (cc_path / 'conf.yml').open('w') as f:
    f.write(sample_conf)
