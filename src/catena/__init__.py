from pathlib import Path
from typing import Optional
import sys
import os

from .jobs.slurm import SlurmJob
from .lib.yaml_loader import Loader, safe_loader
from .models import JobManifest, SlurmSubmit, SlurmModel
import catena.lib.env as env
from .jobs import Manifest, Jobs