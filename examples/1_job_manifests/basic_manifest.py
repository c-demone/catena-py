"""
A first example to show how a series of jobs can be submitted using a yaml manifest
referred to as a 'job manifest'. A basic example of such a job manifest is provided
in the 'sample_manifest' directory as basic_manifest.yml

The scripts that are launched as SLURM jobs can be found in the 'scripts' directory
in the root of the examples directory. They are all basic hello world type programs. 

rich is a great library for nicely printing things to the console. The inspect method 
is used here to expose what the class looks like and what it contains before and after
submitting a job

NOTE: To run this script and have it submit a job, you should add the -s flag
    e.g: python3 basic_manifest-s
"""
import sys
from pathlib import Path

sys.path.append(str(Path(*list(Path(__file__).parent.resolve().parts[:-2]))/"src"))

from  catena import Manifest

manifest = Manifest("sample_manifests/basic_manifest.yaml", _submit=False).open()

for job in manifest.jobs:
    print(job)

if '-s' in sys.argv:
    manifest = Manifest("sample_manifests/basic_manifest.yaml")