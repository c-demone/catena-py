import sys
from pathlib import Path
from rich import print

sys.path.append(str(Path(*list(Path(__file__).parent.resolve().parts[:-2]))/"src"))

from catena import Manifest

# create stdout/stderr directory for jobs
if not Path('complextest/output').is_dir():
    Path('complextest/output').mkdir(mode=0o744)

# parse job definitions from manifest
manifest = Manifest("complextest/complex-manifest.yaml", _submit=False).open()

# inspect jobs (and submit if -s in argv)
for job in manifest.jobs:
    print(job)
    if '-s' in sys.argv:
        job.submit()