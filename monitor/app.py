import asyncio
import aioconsole
from aiomonitor.utils import alt_names
from aiomonitor.mypy_types import Loop, OptLocals
from aiomonitor.utils import (_format_stack, cancel_task, task_by_id,
                                    close_server, alt_names, all_tasks)

from rich.console import Console
from rich import print, box
from rich.table import Table
from rich.align import Align
from rich.panel import Panel
from typing import IO, NamedTuple, Any, Optional, Union
import logging

import selectors
import telnetlib
import contextlib
from docstring_parser import parse
from pyfiglet import Figlet
import functools

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
from typing import (IO, Any, Callable, Optional, Tuple, Generator,
                    List, Type, NamedTuple, Sequence)
from contextlib import suppress
from concurrent.futures import Future  
from terminaltables import AsciiTable


def tabulate(rows: List[List[str]], 
             cols: Optional[List[str]], 
             header: Optional[bool] = True, 
             header_style: Optional[str] = 'bold cyan'):

    """
    Create rich.Table for displaying information in nicely formatted
    table
    """
    
    table = Table(show_header=header, header_style=header_style)

    table.title = "Available commands"
    table.box = box.SQUARE_DOUBLE_HEAD
   
    # add column headers
    for col in cols:
        table.add_column(col)
    
    # add rows
    for row in rows:
        table.add_row(*row)

    table.caption =  '📡 [deep_sky_blue4]Asynchronous Job Monitor[/deep_sky_blue4]'

    # center output in console and return result
    centered_table = Align.center(table)
    return centered_table


def info_panel(title:str, content:str):
    """
    Return titled panel with string content
    """
    return Panel(content,
                 title=f"[cyan]{title}[/cyan]",
                 border_style='deep_sky_blue4',
                 expand=True
                )


Server = asyncio.AbstractServer  


class CommandException(Exception):
    """
    Unexpected command input exception
    """
    pass


class UnknownCommandException(CommandException):
    """
    Unknown command exception
    """
    pass


class MultipleCommandException(CommandException):
    """
    Exception for multiple commands
    """
    def __init__(self, cmds: List['CmdName']) -> None:
        self.cmds = cmds
        super().__init__()


class ArgumentMappingException(CommandException):
    """
    Unexpected argument mapping exceptions
    """
    pass


CmdName = NamedTuple('CmdName', [('cmd_name', str), ('method_name', str)])


log = logging.getLogger(__name__)


_TelnetSelector: selectors.BaseSelector = getattr(
    selectors, 'PollSelector',
    selectors.SelectSelector)


class RichAsyncConsole(aioconsole.AsynchronousConsole):
    """
    Asynchronous console with print overloaded by Rich print
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
        console = Console(file=self)
        console.print(*args, **kwargs)


def console_proxy(sin: IO[str], sout: IO[str], host: str, port: int) -> None:
    """
    Telnet proxy for socket server application
    """
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


def init_console_server(host: str,
                        port: int,
                        locals: OptLocals,
                        loop: Loop,
                        streams=None) -> 'Future[Server]':

    def _factory(streams: Any = streams):
        """
        Asynchronus socket server console factory
        """
        return RichAsyncConsole(locals=locals, streams=streams, loop=loop)


    coro = aioconsole.start_interactive_server(
        host=host, port=port, factory=_factory, loop=loop)
    console_future = asyncio.run_coroutine_threadsafe(coro, loop=loop)
    return console_future



def get_console(file=None) -> Console:
    """
    Get a global instance of rich.console.Console. This is used when rich requires a console
    and hasn't been explicitly given one.
    """
    global _console
    if "_console" not in globals():
        from rich.console import Console

        _console = Console(file=file)
    return _console



class JobMonitor:

    """
    Job monitoring console application
    """

    _event_loop_thread_id = None  # type: int
    _cmd_prefix = 'do_'
    _empty_result = object()

    # ANSI colors for console
    _cesc = '\033[m'
    _cbld = '\033[1m'
    _bgrn = '\033[1;32m'
    _bcyn = '\033[1;36m'
    _bred = '\033[1;31m'
    _byel = '\033[1;33m'
    _grn = '\033[0;32m'
    _red = '\033[0;31m'
    _yel = '\033[0;33m'
    
    # application default prompts
    prompt = 'job monitor >>> '
    banner = Figlet('chunky').renderText('Asynchronous\n    Job Monitor')
    info = '\nCurrently, {tasknum} monitoring task{s} are running\nType help for available commands\n\n'  # noqa
    intro = banner + info
    help_template = '{cmd_short_help}\n\n  {full_arglist}\n\n{cmd_long_help}\n'
    help_short_template = '{cmd_name}{arg_list}: {cmd_short_help}'  # noqa

    _sin = None  # type: IO[str]
    _sout = None  # type: IO[str]

    def __init__(self,
                 loop: Optional[Type[asyncio.AbstractEventLoop]]=asyncio.get_event_loop(), *,
                 jobs: Optional[list] = None,
                 port: Optional[int] = None,
                 console_port: Optional[int] = None,
                 host: str = '0.0.0.0',
                 console_enabled: bool = True,
                 locals: OptLocals = None) -> None:
        self._loop = loop #or asyncio.get_event_loop()
        self.jobs = jobs
        self._host = host
        self._port = port
        self._console_port = console_port
        self._console_enabled = console_enabled
        self._locals = locals # <- use this to insert default variables into console

        self.console = Console()

        log.info('Starting aiomonitor at %s:%d', host, port)

        self._ui_thread = threading.Thread(target=self._server, args=(),
                                           daemon=True)
        self._closing = threading.Event()
        self._closed = False
        self._started = False
        self._console_future: Optional[Future[Any]] = None  # type: Optional[Future[Any]]

        self.lastcmd = None  # type: Optional[str]

    def __repr__(self) -> str:
        """
        Job monitor description
        """
        name = self.__class__.__name__
        return '<{name}: {host}:{port}>'.format(
            name=name, host=self._host, port=self._port)


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
        self.close()

    @property
    def closed(self) -> bool:
        """
        Socket server closed state 
        """
        return self._closed


    @property
    def _port(self):
        return self.__port
    

    @_port.setter
    def _port(self, value:str):
    
        self.__port = value
        if self.__port is None:
            self.__port = self.get_open_port()


    @property
    def _console_port(self):
        return self.__console_port
    

    @_console_port.setter
    def _console_port(self, value:str):
    
        self.__console_port = value
        if self.__console_port is None:
            self.__console_port = self.get_open_port


    def _server(self) -> None:
        """
        TCP socket server
        """
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
        """
        Main interactive loop of the job monitor application
        """
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
        """
        Command dispatcher for console application
        """
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
        """
        Command filter for searching available commands
        """

        cmds = (cmd for cmd in dir(self) if cmd.startswith(self._cmd_prefix))
        for name in cmds:
            if name.startswith(self._cmd_prefix + startswith):
                yield CmdName(name[len(self._cmd_prefix):], name)
            meth = getattr(self, name)
            if with_alts and hasattr(meth, 'alt_names'):
                for altname in meth.alt_names:
                    if altname.startswith(startswith):
                        yield CmdName(altname, name)


    def get_open_port():
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("",0))
        s.listen(1)
        port = s.getsockname()[1]
        s.close()
        return port


    def start(self) -> None:
        """
        Start socket server
        """
        assert not self._closed
        assert not self._started

        self._started = True
        self._event_loop_thread_id = threading.get_ident()
        self._ui_thread.start()


    def close(self) -> None:
        """
        Close socket server
        """
        if not self._closed:
            self._closing.set()
            self._ui_thread.join()
            self._closed = True


    def map_args(self, cmd: Callable[..., Any], args: Sequence[str]
                 ) -> Generator[Any, None, None]:
        """
        Map command arguments from console.

        We iterate over the functions' annotation for its
        parameters and also manually over the given arguments
        (they can have arbitrarily different lengths).
        Here we could be in the situation where a further
        parameter exists, but no argument is given to it.
        Since we might have a method with optional, non-star
        arguments, we must ignore a StopIteration from this call
        to next.
        """
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
                    with suppress(StopIteration):
                        yield type_(next(ia))
            except Exception as e:
                raise ArgumentMappingException(cmd.__name__) from e
        if tuple(ia):
            msg = 'Too many arguments for command {}()'
            raise TypeError(msg.format(cmd.__name__))


    def precmd(self, comm: str, args: Sequence[str]
               ) -> Tuple[Callable[..., Any], List[str]]:
        """
        Pre-command hook
        """
        cmd = self.getcmd(comm)
        return cmd, list(self.map_args(cmd, args))


    def postcmd(self,
                comm: str,
                args: Sequence[str],
                result: Any,
                exception: Optional[Exception] = None) -> None:
        """
        Post command hook
        """
        if (exception is not None
                and not isinstance(exception, (CommandException, TypeError))):
            raise exception

    def getcmd(self, comm: str) -> Callable[..., Any]:
        """
        Get command by name and return corresponding method
        """
        allcmds = sorted(self._filter_cmds(startswith=comm))
        if not allcmds:
            raise UnknownCommandException(comm)
        if len(allcmds) > 1 and allcmds[0].cmd_name != comm:
            raise MultipleCommandException(allcmds)
        return getattr(self, allcmds[0].method_name)  # type: ignore

    def emptyline(self) -> None:
        """
        Handle no user input in interactive application loop
        """
        if self.lastcmd is not None:
            self._command_dispatch(self.lastcmd)

    def default(self, comm: str, *args: str) -> None:
        """
        Default missing command dialogue
        """
        self._sout.write('No such command: {}\n'.format(comm))
    
    
    def query_yes_no(question, default="yes"):
        """Ask a yes/no question via raw_input() and return their answer.

        "question" is a string that is presented to the user.
        "default" is the presumed answer if the user just hits <Enter>.
                It must be "yes" (the default), "no" or None (meaning
                an answer is required of the user).

        The "answer" return value is True for "yes" or False for "no".
        """
        valid = {"yes": True, "y": True, "ye": True, "no": False, "n": False}
        if default is None:
            prompt = " [y/n] "
        elif default == "yes":
            prompt = " [Y/n] "
        elif default == "no":
            prompt = " [y/N] "
        else:
            raise ValueError("invalid default answer: '%s'" % default)

        while True:
            sys.stdout.write(question + prompt)
            choice = input().lower()
            if default is not None and choice == "":
                return valid[default]
            elif choice in valid:
                return valid[choice]
            else:
                sys.stdout.write("Please respond with 'yes' or 'no' " "(or 'y' or 'n').\n")


    @alt_names('? h')
    def do_help(self, *cmd_names: str) -> None:
        """show help for command name (help help for usage)

        Usage:
        help <cmd> <cmd_a> ... 
            (or h <cmd <cmd_a> ...)

        Parameters
        ----------
        cmd: Union[List[str], str] 
            Command(s) for which to display help
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

                arglist = [f'[bold turquoise4]{i.arg_name}[/bold turquoise4]:: [gold1]{i.type_name}[/gold1]'
                                if 'None' not in i.arg_name else '[bold red3]None[/bold red3]' for i in _help.params]

                full_arglist = [f'[bold turquoise4]{i.arg_name}[/bold turquoise4]:: [gold1]{i.type_name}[/gold1]: {i.description}'
                                    if 'None' not in i.arg_name else '[bold red3]None[/bold red3]' 
                                    for i in _help.params]

                row_data = ([f"[bold cyan]{cmd[len(self._cmd_prefix):]}[/bold cyan]",
                                "|".join(arglist),
                                f"[grey85]{_help.short_description}[/grey85]"])
                if cmd_names:
                    long_help = template.format(
                                    cmd_long_help=str(_help.long_description),
                                    cmd_short_help=f"[cyan]{_help.short_description}[/cyan]",
                                    full_arglist='\n'.join(full_arglist))

                    return cmd[len(self._cmd_prefix):], long_help 
                else:
                    return row_data

        if not cmd_names:
            # generic help to print all commands
            console = Console(file=self._sout, color_system='truecolor')
            row_data = []

            cmds = sorted(
                c.method_name for c in self._filter_cmds(with_alts=False)
            )
            for cmd in cmds:
                row_data.append(_h(cmd, self.help_short_template))
            table = tabulate(rows=row_data, cols=['command', 'arguments', 'description'])
            console.print(table)
        else:
            console = Console(file=self._sout, color_system='truecolor')
            if len(cmd_names) == 1 and 'all' in cmd_names:
                cmd_names = sorted(c.method_name for c in 
                                    self._filter_cmds(with_alts=False))

                for cmd in cmd_names:
                    name, info = _h(cmd, self.help_template)
                    console.print(info_panel(title=name, content=info))
            else:
                for cmd in cmd_names:
                    name, info = _h(self._cmd_prefix + cmd, self.help_template)
                    console.print(info_panel(title=name, content=info))                 


    @alt_names('p')
    def do_ps(self) -> None:
        """Show task table
        Usage:
        ps (or p)

        Parameters
        ----------
        None
        """
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
        """Show stack frames for a task
        
        Usage:
        where  <taskid> (or w <taskid>)

        Parameters
        ----------
        taskid : int
            The task id for which to show stack frames
        """
        task = task_by_id(taskid, self._loop)
        if task:
            self._sout.write(_format_stack(task))
            self._sout.write('\n')
        else:
            self._sout.write('No task %d\n' % taskid)


    def do_signal(self, signame: str) -> None:
        """
        Send a Unix signal
        
        Usage:
        signal <unixsig>

        Parameters
        ----------
        unixsig: str
            Unix signal to execute (e.g SIGTERM)
        """
        if hasattr(signal, signame):
            os.kill(os.getpid(), getattr(signal, signame))
        else:
            self._sout.write('Unknown signal %s\n' % signame)


    @alt_names('st')
    def do_stacktrace(self) -> None:
        """Print a stack trace from the event loop thread
        
        Usage:
        stacktrace (or st)

        Parameters
        ----------
        None
        """
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
        """Suspend job monitor application in background

        Usage:
        quit (or q)

        Parameters
        ----------
        None
        """
        self._sout.write(f'{self._grn}Use Ctrl-C to suspend monitor{self._cesc}\n')
        self._sout.flush()


    def do_console(self) -> None:
        """Switch to async Python REPL

        Usage:
        console

        Parameters
        ----------
        None        
        """
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
    def do_jobs(self, jobid: Optional[Union[List[int], int]] = None):
        """Display job objects with current job information

        Usage:
        jobs <jobid>

        Parameters
        ----------
        jobid: Optional[Union[List[int], int]]
            Optional job id for which to view job information
        """
        console = Console(file=self._sout, color_system='truecolor')
        if self.jobs is not None:
            console.print(self.jobs.brief()) 
        else:
            console.print("[bold orange]no jobs to show[/bold orange]")
    
    @alt_names('-k')
    def do_kill(self):
        """kill monitoring application permanently!
        
        Usage:
        kill

        Parameters
        ----------
        None
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
        """
        Start job monitor application
        """

        m = cls(loop, jobs=jobs, host=host, 
                port=port, console_port=console_port,
                console_enabled=console_enabled, locals=locals)
        m._sin = stdin
        m._sout = stdout
        m.start()
        loop.run_forever()