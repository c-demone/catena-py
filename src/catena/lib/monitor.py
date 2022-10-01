"""
Example implementation of a monitoring Daemon process that can be access through netcat
and will run the monitoring process in console, or allow access to console that has
locals() made available to it
"""



import asyncio
import aiomonitor
from aiomonitor.utils import alt_names
from aiomonitor.mypy_types import Loop, OptLocals
from typing import Optional, List, Type
import daemon

from rich.console import Console
from rich import print
import rich

# direct copy
import inspect
import logging
import os
import signal
import socket
import sys
import threading
import traceback
from textwrap import wrap
from types import TracebackType
from typing import (IO, Dict, Any, Callable, Optional, Tuple, Generator,  # noqa
                    List, Type, TypeVar, NamedTuple, get_type_hints,  # noqa
                    cast, Sequence)  # noqa
from contextlib import suppress
from concurrent.futures import Future  # noqa

from terminaltables import AsciiTable
import aioconsole

from aiomonitor.utils import (_format_stack, cancel_task, task_by_id, #console_proxy,
                    close_server, alt_names, all_tasks)

from daemon.daemon import (prevent_core_dump, change_file_creation_mask, 
                    change_working_directory, change_process_owner, detach_process_context,
                    make_default_signal_map, set_signal_handlers, close_all_open_files,
                    redirect_stream, is_detach_process_context_required)

import tempfile
from pathlib import Path
import daemon.pidfile
import os, sys
import signal
import psutil
import uuid
import functools

from service import Service, _PIDFile

import sys, os, time, atexit, signal
import telnetlib
import contextlib
import selectors
from docstring_parser import parse
from pyfiglet import Figlet

MONITOR_HOST = '127.0.0.1' # Empty string listen on all interfaces
MONITOR_PORT = 50101
CONSOLE_PORT = 50102


Server = asyncio.AbstractServer  # noqa
console = Console()

class CommandException(Exception):
    pass


class UnknownCommandException(CommandException):
    pass


class MultipleCommandException(CommandException):
    def __init__(self, cmds: List['CmdName']) -> None:
        self.cmds = cmds
        super().__init__()


class ArgumentMappingException(CommandException):
    pass


CmdName = NamedTuple('CmdName', [('cmd_name', str), ('method_name', str)])
log = logging.getLogger(__name__)


_TelnetSelector = getattr(
    selectors, 'PollSelector',
    selectors.SelectSelector)  # Type: selectors.BaseSelector

def console_proxy(sin: IO[str], sout: IO[str], host: str, port: int) -> None:
    tn = telnetlib.Telnet()
    with contextlib.closing(tn):
        tn.open(host, port, timeout=10)
        with _TelnetSelector() as selector:
            selector.register(tn, selectors.EVENT_READ)
            selector.register(sin, selectors.EVENT_READ)

            while True:
                for key, _ in selector.select():
                    if key.fileobj is tn:
                        try:
                            data = tn.read_very_eager()
                        except EOFError:
                            print('*Connection closed by remote host*')
                            return

                        if data:
                            try:
                                sout.write(data.decode('utf-8'))
                                sout.flush()
                            except Exception:
                                data = tn.read_all()
                                sout.write(data.decode('utf-8'))
                                sout.flus()
                    else:
                        resp = sin.readline()
                        if not resp:
                            return
                        tn.write(resp.encode('utf-8'))

def get_console(file=None) -> "Console":
    """Get a global :class:`~rich.console.Console` instance. This function is used when Rich requires a Console,
    and hasn't been explicitly given one.
    Returns:
        Console: A console instance.
    """
    global _console
    if "_console" not in globals():
        from rich.console import Console

        _console = Console(file=file)

    return _console

class RichAsyncConsole(aioconsole.AsynchronousConsole):

    """
    Extension to aioconsole.AsynchronousConsole to support Python
    Rich library for printing to console.
    """

    def __init__(self, 
                 streams=None,
                 locals=None,
                 filename="<console>",
                 prompt_control=None,
                 loop=None):

        super().__init__(streams, locals, filename, prompt_control)
        

    
    @functools.wraps(print)
    def print(self, *args, **kwargs):

        #out_monitor = open('._monitor_out_.out', 'w')
        #if self.locals.get('_console') is None:
        #    self.locals

        
        console = Console(file=self)
        console.print(*args, **kwargs)

        


def init_console_server(host: str,
                        port: int,
                        locals: OptLocals,
                        loop: Loop,
                        streams=None) -> 'Future[Server]':

    """
    Initialize monitor console server: adapted from aiomonitor
    """
    def _factory(streams: Any = streams):
        return RichAsyncConsole(locals=locals, streams=streams, loop=loop)

    coro = aioconsole.start_interactive_server(
        host=host, port=port, factory=_factory, loop=loop)
    console_future = asyncio.run_coroutine_threadsafe(coro, loop=loop)
    return console_future


class JobMonitor:

    """
    Job monitoring TCP socket server based adapted 
    from aioconsole/aiomonitor
    """

    _event_loop_thread_id = None  # type: int
    _cmd_prefix = 'do_'
    _empty_result = object()

    _cesc = '\033[m'
    _cbld = '\033[1m'
    _bgrn = '\033[1;32m'
    _bcyn = '\033[1;36m'
    _bred = '\033[1;31m'
    _byel = '\033[1;33m'
    _grn = '\033[0;32m'
    _red = '\033[0;31m'
    _yel = '\033[0;33m'
    
    prompt = 'job monitor >>> '
    banner = Figlet('chunky').renderText('Asynchronous\n    Job Monitor')
    info = '\nCurrently, {tasknum} monitoring task{s} are running\nType help for available commands\n\n'  # noqa
    intro = banner + info
    help_template = '\n{cmd_name}: {cmd_short_help}\n{full_arglist}\n\n{cmd_long_help}\n'
    help_short_template = '{cmd_name}{cmd_arg_sep}{arg_list}: {cmd_short_help}'  # noqa

    _sin = None  # type: IO[str]
    _sout = None  # type: IO[str]

    def __init__(self,
                 loop: Optional[Type[asyncio.AbstractEventLoop]]=asyncio.get_event_loop(), *,
                 jobs: Optional[list] = None,
                 host: str = '127.0.0.1',
                 port: int = MONITOR_PORT,
                 console_port: int = CONSOLE_PORT,
                 console_enabled: bool = True,
                 locals: OptLocals = None) -> None:
        self._loop = loop #or asyncio.get_event_loop()
        self.jobs = jobs

        # port and console port should be properties that are set by searching
        # for open port in a range of say 1000 ports
        self._host = host
        self._port = port
        self._console_port = console_port
        self._console_enabled = console_enabled
        self._locals = locals

        self.console = Console()

        log.info('Starting aiomonitor at %s:%d', host, port)

        self._ui_thread = threading.Thread(target=self._server, args=(),
                                           daemon=True)
        self._closing = threading.Event()
        self._closed = False
        self._started = False
        self._console_future = None  # type: Optional[Future[Any]]

        self.lastcmd = None  # type: Optional[str]

    def __repr__(self) -> str:
        name = self.__class__.__name__
        return '<{name}: {host}:{port}>'.format(
            name=name, host=self._host, port=self._port)

    def start(self) -> None:
        assert not self._closed
        assert not self._started

        self._started = True
        self._event_loop_thread_id = threading.get_ident()
        self._ui_thread.start()
        #exit()

    @property
    def closed(self) -> bool:
        return self._closed

    def __enter__(self) -> 'Monitor':
        #if not self._started:
        #    self.start()
        return self

    # exc_type should be Optional[Type[BaseException]], but
    # this runs into https://github.com/python/typing/issues/266
    # on Python 3.5.
    def __exit__(self, exc_type: Any,
                 exc_value: Optional[BaseException],
                 traceback: Optional[TracebackType]) -> None:
        self.close()

    def _find_open_port(self, 
                        hostname: Optional[str] = None,
                        start: Optional[int] = 8000,
                        end: Optional[int] = 65535):
        
        if hostname is None:
            hostname = socket.gethostname()
        
        target = socket.gethostbyname(hostname)
        
        try:
            # scan ports in range
            for port in range(start, end):
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                socket.setdefaulttimeout(1)

                # return error indicator
                result = s.connect_ex(target, port),

                if result == 0:
                    s.close()
                    return port
                
                s.close()
            
        except socket.gaierror:
            print("\n Hostname could not be resolved")
        
        except socket.error:
            print("\n Server not responding")


    def close(self) -> None:
        if not self._closed:
            self._closing.set()
            self._ui_thread.join()
            self._closed = True

    def _server(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except AttributeError:
            pass

        # set the timeout to prevent the server loop from
        # blocking indefinitaly on sock.accept()
        sock.settimeout(0.5)
        sock.bind((self._host, self._port))
        sock.listen(1)
        with sock:
            while not self._closing.is_set():
                try:
                    client, addr = sock.accept()
                    with client:
                        sout = client.makefile('w', encoding='utf-8')
                        sin = client.makefile('r', encoding='utf-8')
                        self._interactive_loop(sin, sout)
                except (socket.timeout, OSError):
                    continue

    def _interactive_loop(self, sin: IO[str], sout: IO[str]) -> None:
        """Main interactive loop of the monitor"""
        self._sin = sin
        self._sout = sout
        tasknum = len(all_tasks(loop=self._loop))
        s = '' if tasknum == 1 else 's'
        self._sout.write(self.intro.format(tasknum=tasknum, s=s))
        try:
            while not self._closing.is_set():
                self._sout.write(self.prompt)
                self._sout.flush()
                try:
                    user_input = sin.readline()
                    if not user_input:
                        break
                    user_input = user_input.strip()
                except Exception as e:
                    msg = 'Could not read from user input due to:\n{}\n'
                    log.exception(msg)
                    self._sout.write(msg.format(repr(e)))
                    self._sout.flush()
                else:
                    try:
                        self._command_dispatch(user_input)
                    except Exception as e:
                        msg = 'Unexpected Exception during command execution:\n{}\n'  # noqa
                        log.exception(msg)
                        self._sout.write(msg.format(repr(e)))
                        self._sout.flush()
        finally:
            self._sin = None  # type: ignore
            self._sout = None  # type: ignore

    def _command_dispatch(self, user_input: str) -> None:
        if not user_input:
            return self.emptyline()

        self.lastcmd = user_input
        comm, *args = user_input.split(' ')
        try:
            cmd, args = self.precmd(comm, args)
            result = cmd(*args)
        except UnknownCommandException as e:
            result = self._empty_result
            caught_ex = e  # type: Optional[Exception]
            self.default(comm, *args)
        except MultipleCommandException as e:
            result = self._empty_result
            caught_ex = e
            msg = 'Ambiguous command "{}"'.format(comm)
            self._sout.write(msg + '\n')
        except ArgumentMappingException as e:
            result = self._empty_result
            caught_ex = e
            msg = 'An argument to {} could not be converted according to the methods type annotation because of this error:\n{}\n'  # noqa
            self._sout.write(msg.format(e, repr(e.__cause__)))
        except TypeError as e:
            result = self._empty_result
            caught_ex = e
            msg = 'Probably incorrect number of arguments to command method:\n{}\n'  # noqa
            self._sout.write(msg.format(repr(e)))
        except Exception as e:
            result = self._empty_result
            caught_ex = e
        else:
            caught_ex = None
        finally:
            self.postcmd(comm, args, result, caught_ex)

    def _filter_cmds(self, *,
                     startswith: str = '',
                     with_alts: bool = True) -> Generator[CmdName, None, None]:
        cmds = (cmd for cmd in dir(self) if cmd.startswith(self._cmd_prefix))
        for name in cmds:
            if name.startswith(self._cmd_prefix + startswith):
                yield CmdName(name[len(self._cmd_prefix):], name)
            meth = getattr(self, name)
            if with_alts and hasattr(meth, 'alt_names'):
                for altname in meth.alt_names:
                    if altname.startswith(startswith):
                        yield CmdName(altname, name)

    def map_args(self, cmd: Callable[..., Any], args: Sequence[str]
                 ) -> Generator[Any, None, None]:
        params = inspect.signature(cmd).parameters.values()
        ia = iter(args)
        for param in params:
            if (param.annotation is param.empty or
                    not callable(param.annotation)):

                def type_(x: Any) -> Any:
                    return x

            else:
                type_ = param.annotation
            try:
                if str(param).startswith('*'):
                    for arg in ia:
                        yield type_(arg)
                else:
                    # We iterate over the functions' annotation for its
                    # parameters and also manually over the given arguments
                    # (they can have arbitrarily different lengths).
                    # Here we could be in the situation where a further
                    # parameter exists, but no argument is given to it.
                    # Since we might have a method with optional, non-star
                    # arguments, we must ignore a StopIteration from this call
                    # to next.
                    with suppress(StopIteration):
                        yield type_(next(ia))
            except Exception as e:
                raise ArgumentMappingException(cmd.__name__) from e
        if tuple(ia):
            msg = 'Too many arguments for command {}()'
            raise TypeError(msg.format(cmd.__name__))

    def precmd(self, comm: str, args: Sequence[str]
               ) -> Tuple[Callable[..., Any], List[str]]:
        cmd = self.getcmd(comm)
        return cmd, list(self.map_args(cmd, args))

    def postcmd(self,
                comm: str,
                args: Sequence[str],
                result: Any,
                exception: Optional[Exception] = None) -> None:
        if (exception is not None
                and not isinstance(exception, (CommandException, TypeError))):
            raise exception

    def getcmd(self, comm: str) -> Callable[..., Any]:
        allcmds = sorted(self._filter_cmds(startswith=comm))
        if not allcmds:
            raise UnknownCommandException(comm)
        if len(allcmds) > 1 and allcmds[0].cmd_name != comm:
            raise MultipleCommandException(allcmds)
        return getattr(self, allcmds[0].method_name)  # type: ignore

    def emptyline(self) -> None:
        if self.lastcmd is not None:
            self._command_dispatch(self.lastcmd)

    def default(self, comm: str, *args: str) -> None:
        self._sout.write('No such command: {}\n'.format(comm))
    

    @alt_names('? h')
    def do_help(self, *cmd_names: str) -> None:
        """Show help for command name
        Any number of command names may be given to help, and the long help
        text for all of them will be shown.
        """
        def _h(cmd: str, template: str) -> None:
            try:
                func = getattr(self, cmd)
            except AttributeError:
                self._sout.write('{}No such command{}: {}\n'.format(self._bred,
                    self._cesc,cmd))
            else:
                doc = func.__doc__ if func.__doc__ else ''
                _help = parse(doc)

                arglist = [f'{i.arg_name}:<{self._byel}{i.type_name}{self._cesc}>' for i in _help.params]

                full_arglist = [f'    {self._cbld}{i.arg_name}{self._cesc}<{self._byel}{i.type_name}{self._cesc}>: {i.description}'
                                     for i in _help.params]
                
                
                self._sout.write(
                    template.format(
                        cmd_name=f'{self._bcyn}{cmd[len(self._cmd_prefix):]}{self._cesc}',
                        arg_list=f'({", ".join(arglist)})',
                        cmd_arg_sep=' ' if arglist else '',
                        cmd_long_help=f"{self._cbld}{str(_help.long_description)}{self._cesc}",
                        cmd_short_help=_help.short_description,
                        full_arglist='\n'.join(full_arglist)
                    ) + '\n'
                )

        if not cmd_names:
            # generic help to print all commands
            cmds = sorted(
                c.method_name for c in self._filter_cmds(with_alts=False)
            )
            self._sout.write('Available Commands are:\n\n')
            for cmd in cmds:
                _h(cmd, self.help_short_template)
        else:
            for cmd in cmd_names:
                _h(self._cmd_prefix + cmd, self.help_template)


    @alt_names('p')
    def do_ps(self) -> None:
        """Show task table"""
        headers = ('Task ID', 'State', 'Task')
        table_data = [headers]
        for task in sorted(all_tasks(loop=self._loop), key=id):
            taskid = str(id(task))
            if task:
                t = '\n'.join(wrap(str(task), 80))
                table_data.append((taskid, task._state, t))
        table = AsciiTable(table_data)
        self._sout.write(table.table)
        self._sout.write('\n')
        self._sout.flush()

    @alt_names('w')
    def do_where(self, taskid: int) -> None:
        """Show stack frames for a task"""
        task = task_by_id(taskid, self._loop)
        if task:
            self._sout.write(_format_stack(task))
            self._sout.write('\n')
        else:
            self._sout.write('No task %d\n' % taskid)

    def do_signal(self, signame: str) -> None:
        """Send a Unix signal"""
        if hasattr(signal, signame):
            os.kill(os.getpid(), getattr(signal, signame))
        else:
            self._sout.write('Unknown signal %s\n' % signame)

    @alt_names('st')
    def do_stacktrace(self) -> None:
        """Print a stack trace from the event loop thread"""
        frame = sys._current_frames()[self._event_loop_thread_id]
        traceback.print_stack(frame, file=self._sout)

    def do_cancel(self, taskid: int) -> None:
        """Cancel the indicated task by id
        
        Usage:
        cancel <taskid>

        Parameters
        ----------
        taskid : int
            The task id of the task to cancel
        
        """
        task = task_by_id(taskid, self._loop)
        if task:
            fut = asyncio.run_coroutine_threadsafe(
                cancel_task(task), loop=self._loop)
            fut.result(timeout=3)
            self._sout.write('Cancel task %d\n' % taskid)
        else:
            self._sout.write('No task %d\n' % taskid)

    @alt_names('quit q')
    def do_exit(self) -> None:
        """Leave the monitor"""
        self._sout.write(f'{self._grn}Use Ctrl-C to suspend monitor{self._cesc}\n')
        self._sout.flush()

    def do_console(self) -> None:
        """Switch to async Python REPL"""
        if not self._console_enabled:
            self._sout.write(f'{self._yel}Python console disabled for this sessiong{self._cesc}\n')
            self._sout.flush()
            return

        h, p = self._host, self._console_port
        log.info('Starting console at %s:%d', h, p)
        fut = init_console_server(
            self._host, self._console_port, self._locals, self._loop, streams=[self._sin, self._sout])
        self._sout.write("FUTURE")
        server = fut.result(timeout=3)
        try:
            console_proxy(
                self._sin, self._sout, self._host, self._console_port)
        finally:
            coro = close_server(server)
            close_fut = asyncio.run_coroutine_threadsafe(coro, loop=self._loop)
            close_fut.result(timeout=15)

    @alt_names('-m')
    def do_jobs(self, jobid: Optional[str] = None):
        """Run job monitoring application in foreground

        There is one optional argument, "name".  This name argument must be
        provided with proper URL excape codes, like %20 for spaces.
        """
        console = Console(file=self._sout)
        if self.jobs is not None:
            console.print(self.jobs.brief()) 
        else:
            console.print("[bold orange]no jobs to show[/bold orange]")
    
    @alt_names('-k')
    def do_kill(self):
        """kill monitoring process
        """
        self._sout.write(f'{self._bred}Monitor killed - use Ctrl-C to exit{self._cesc}\n')
        self._sout.flush()
        os._exit(100)
    
    @classmethod
    def start_monitor(cls, loop: Loop, *,
                jobs: Optional[list] = None,
                host: str = '127.0.0.1',
                port: int = 50101,
                console_port: int = 50102,
                console_enabled: bool = True,
                locals: Optional[dict] = None,
                stdin=None,
                stdout=None,
                stderr=None):

        m = cls(loop, jobs=jobs, host=host, 
                port=port, console_port=console_port,
                console_enabled=console_enabled, locals=locals)
        m._sin = stdin
        m._sout = stdout
        m.start()
        loop.run_forever()

        #return m

        


class Monitor:
    """
    A Monitor object that will run monitoring server as a 
    background process/daemon.

    Usage: subclass the daemon class and override the run() method.
    """
    
    monitor = JobMonitor

    def __init__(self, 
                 jobs: list,
                 working_directory: Optional[str] = os.getcwd(),
                 umask: Optional[int] = 0,
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

    @property
    def is_open(self):
        return self._is_open

    def daemonize(self):
        """Deamonize class. UNIX double fork mechanism."""


        if self.is_open:
            return
        
        #if self.prevent_core:
        #    prevent_core_dump()SSS
 
        change_file_creation_mask(self.umask)
        #change_working_directory(self.working_directory)
        change_process_owner(self.uid, self.gid, self.initgroups)
 
        if self.detach_process:
            sys.stdout.write('Detaching monitoring process...\n')
            detach_process_context()
        #if self.detach_process:
        #sys.stdout.write('Detaching monitoring process...\n')
        #try: 
        #    pid = os.fork() 
        #    if pid > 0:
        #        # exit first parent
        #        sys.exit(0) 
        #except OSError as err: 
        #    sys.stderr.write('fork #1 failed: {0}\n'.format(err))
        #    sys.exit(1)
       # 
        # decouple from parent environment
        #os.chdir('/') 
        #os.setsid() 
        #os.umask(self.umask) 
    
        # do second fork
        #try: 
        #    pid = os.fork() 
        #    if pid > 0:
        #        sys.stdout.write(str(pid))
        #        # exit from second parent
        #        self.pidfile.__enter__()
        #        sys.exit(0) 
        #except OSError as err: 
        #    sys.stderr.write('fork #2 failed: {0}\n'.format(err))
        #    sys.exit(1) 

        # redirect standard file descriptors
        redirect_stream(sys.stdin, self.stdin)
        redirect_stream(sys.stdout, self.stdout)
        redirect_stream(sys.stderr, self.stderr)

        self.pidfile.__enter__()

        atexit.register(self.delpid)
        self._is_open = True

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
        self.monitor.start_monitor(loop=loop, jobs=self.jobs, locals=self.locals,
                        stdin=self.stdin, stdout=self.stdout)