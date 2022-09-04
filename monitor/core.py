import asyncio
from typing import Optional, List, Type
import daemon
from rich.console import Console

# direct copy
import os
import sys
import atexit
import signal
import sys
import uuid
import daemon.pidfile
from pathlib import Path
from typing import Optional, List, Type, Any
from types import TracebackType

from aiomonitor.utils import alt_names

from daemon.daemon import (change_file_creation_mask, change_process_owner,
                           detach_process_context, make_default_signal_map, 
                           redirect_stream, _get_file_descriptor)

from .app import JobMonitor

console = Console()

class Monitor:
    """
    A Monitor object that will run monitoring process as a daemone.

    Usage: subclass the daemon class and override the run() method.
    """
    
    monitor = JobMonitor

    def __init__(self, 
                 jobs: list,
                 working_directory: Optional[str] = os.getcwd(),
                 umask: Optional[int] = 0,
                 port: Optional[int] = None,
                 uid: Optional[int] = None,
                 gid: Optional[int] = None,
                 initgroups: Optional[bool] = False,
                 prevent_core: Optional[bool] = True,
                 files_preserve: Optional[list] = None,
                 detach: Optional[bool] = True,
                 pidfile: Optional[str] = None,
                 stdin=None, 
                 stdout=None,
                 stderr=None,
                 signal_map=None): 

        self.jobs = jobs
        self.working_directory = working_directory
        self.umask = umask
        self.port = port
        self.files_preserve = files_preserve
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.prevent_core = True


        if uid is None:
            uid = os.getuid()
        self.uid = uid

        if gid is None:
            gid = os.getgid()
        self.gid = gid

        self.initgroups = initgroups

        self.detach_proces = detach

        if signal_map is None:
            signal_map = make_default_signal_map()
        self.signal_map = signal_map

        if pidfile is None:
            name = f'{Path(sys.argv[0]).stem}_' + str(uuid.uuid4())
            self.pidfile_path =str(os.getcwd() / Path(name)) + '.pid'
        else:
            self.pidfile_path = os.getcwd() / Path(pidfile)
        
        self.pidfile = daemon.pidfile.PIDLockFile(str(self.pidfile_path))
        self.detach_process = detach


        self.locals = locals()
        self.locals.setdefault('pidfile', self.pidfile)
        self.locals['jobs'] = self.jobs
        self.locals.setdefault('context', self)

        self._is_open = False

        atexit.register(self.stop)
        from rich import inspect
        inspect(self)


    def __enter__(self) -> 'Monitor':
        """
        Open context manager
        """
        return self


    def __exit__(self, exc_type: Any,
                 exc_value: Optional[BaseException],
                 traceback: Optional[TracebackType]) -> None:
        """
        Close context
        """
        self.stop()


    def _get_exclude_file_descriptors(self):
        """ Get the set of file descriptors to exclude closing.
 
            :return: A set containing the file descriptors for the
                files to be preserved.
 
            The file descriptors to be preserved are those from the
            items in `files_preserve`, and also each of `stdin`,
            `stdout`, and `stderr`. For each item:
 
            * If the item is ``None``, omit it from the return set.
 
            * If the item's `fileno` method returns a value, include
              that value in the return set.
 
            * Otherwise, include the item verbatim in the return set.
            """
        files_preserve = self.files_preserve
        if files_preserve is None:
            files_preserve = []
        files_preserve.extend(
                item for item in {self.stdin, self.stdout, self.stderr}
                if hasattr(item, 'fileno'))
 
        exclude_descriptors = set()
        for item in files_preserve:
            if item is None:
                continue
            file_descriptor = _get_file_descriptor(item)
            if file_descriptor is not None:
                exclude_descriptors.add(file_descriptor)
            else:
                exclude_descriptors.add(item)
 
        return exclude_descriptors
 

    def _make_signal_handler(self, target):
        """ 
        Make the signal handler for a specified target object.

        :param target: A specification of the target for the
            handler; see below.
        :return: The value for use by `signal.signal()`.

        If `target` is ``None``, return ``signal.SIG_IGN``. If `target`
        is a text string, return the attribute of this instance named
        by that string. Otherwise, return `target` itself.
        """
        if target is None:
            result = signal.SIG_IGN
        elif isinstance(target, str):
            name = target
            result = getattr(self, name)
        else:
            result = target

        return result


    def _make_signal_handler_map(self):
        """ 
        Make the map from signals to handlers for this instance.
 
            :return: The constructed signal map for this instance.
 
            Construct a map from signal numbers to handlers for this
            context instance, suitable for passing to
            `set_signal_handlers`.
        """
        signal_handler_map = dict(
                (signal_number, self._make_signal_handler(target))
                for (signal_number, target) in self.signal_map.items())
        return signal_handler_map


    @property
    def is_open(self):
        return self._is_open


    def daemonize(self):
        """Deamonize class. UNIX double fork mechanism."""


        if self.is_open:
            return
 
        change_file_creation_mask(self.umask)
        #change_working_directory(self.working_directory)
        change_process_owner(self.uid, self.gid, self.initgroups)
 
        if self.detach_process:
            sys.stdout.write('Detaching monitoring process...\n')
            detach_process_context()

        # redirect standard file descriptors
        redirect_stream(sys.stdin, self.stdin)
        redirect_stream(sys.stdout, self.stdout)
        redirect_stream(sys.stderr, self.stderr)

        self.pidfile.__enter__()

        atexit.register(self.delpid)
        self._is_open = True
	
    def terminate(self, signal_number, stack_frame):
        """ Signal handler for end-process signals.
 
            :param signal_number: The OS signal number received.
            :param stack_frame: The frame object at the point the
                signal was received.
            :return: ``None``.
 
            Signal handler for the ``signal.SIGTERM`` signal. Performs the
            following step:
 
            * Raise a ``SystemExit`` exception explaining the signal.
            """
        exception = SystemExit(
                "Terminating on signal {signal_number!r}".format(
                    signal_number=signal_number))
        raise exception


    def delpid(self):
        os.remove(self.pidfile_path)

    def start(self):
        """Start the daemon."""

        # Start the daemon
        self.daemonize()
        self.run()

    def stop(self):
        """Stop the daemon."""

        if not self.is_open:
            return

        if self.pidfile is not None:
            self.pidfile.__exit__(None, None, None)

        self._is_open = False


    def restart(self):
        """Restart the daemon."""
        self.stop()
        self.start()


    def run(self):
        """You should override this method when you subclass Daemon.
        
        It will be called after the process has been daemonized by 
        start() or restart()."""
        
        loop = asyncio.get_event_loop()
        self.monitor.start_monitor(loop=loop, jobs=self.jobs, port=self.port, 
                                   locals=self.locals, stdin=self.stdin, 
                                   stdout=self.stdout)