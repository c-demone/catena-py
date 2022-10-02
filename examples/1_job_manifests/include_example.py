import sys
import os
from pathlib import Path
from rich import inspect, print

sys.path.append(str(Path(*list(Path(__file__).parent.resolve().parts[:-2]))/"src"))

from catena import Manifest

manifest = Manifest("sample_manifests/include_example/advanced_manifest.yml", _submit=False).open()

for job in manifest.jobs:
    print(job)
    
if '-s' in sys.argv:
    manifest = Manifest("sample_manifests/basic_manifest.yml").open()

manifest.close()