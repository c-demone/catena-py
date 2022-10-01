from setuptools import sandbox
from setuptools.command.easy_install import chmod, current_umask
from setuptools.sandbox import DirectorySandbox
from autoflake import fix_code, detect_encoding, open_with_encoding
import nbformat
import importlib.resources as pkg_resources
import pathlib
import jinja2
from jinja2 import Environment, PackageLoader, select_autoescape, StrictUndefined
from typing import Optional, List
from charset_normalizer import from_path
import contextlib
import os

from ..models import lang_extensions 
from . import env


@contextlib.contextmanager
def set_context(path):
    """
    Context manager to set the context of the running script to 
    a specified path
    """

    # current working directory
    cwd = os.getcwd()
    
    # if path is None do not chdir in context
    chdir = True
    if path is None:
        chdir = False

    try:
        if chdir: 
            os.chdir(path)
        yield
    finally:
        if chdir:
            os.chdir(cwd)
        else:
            pass


def _execfile(template, globals=dict(__file__='script.py', 
            __name__='__main__'), filename='script.py', 
            locals=None):
    """
    Adaptation of execfile for rendered jinja template
    Args:
        template(str): rendered jinja2 template for setup.py
        globals(dict): methods that should be globally accesible
        filename(str): name of file from which script was loaded (
            if not read from string, just use any name but should
            matcht __file__ in globals)
        locals(str): mapping object
    """
    if locals is None:
        locals = globals
    code = compile(template, filename, 'exec')
    exec(code, globals, locals)


def _read_code(fpath):
    """
    Reads pysource and removes unused imports
    Args:
        fpath(str): path to pysource (.py file)
    
    Returns:
        (str): flaked source code
    """
    if fpath.endswith(".ipynb"):
        nb = nbformat.read(fpath, as_version=4)
        code = ""
        for cell in nb.cells:
            if cell.cell_type == "code":
                code += cell.source + "\n"
        return code
    elif fpath.endswith(".py") or "." not in fpath:
        encoding = detect_encoding(fpath)
        with open_with_encoding(fpath, encoding=encoding) as f:
            code = f.read()
            return fix_code(code, remove_all_unused_imports=True)
    return None


class classproperty(object):
    '''
    Decorator for class property
    '''
    def __init__(self, getter):
        self.getter = getter

    def __get__(self, instance, owner):
        return self.getter(owner)


class VirtualScriptClass(type):
    """
    MetaClass for VirtualScript classes
    """

    def __str__(self):
        return self.name

    def __unicode__(self):
        return self.name


class VirtualScript(object):
    """
    Base Virtual Script File
    # Adapated from PyPi license
    """
   
    __metaclass__ = VirtualScriptClass

    jinja_env = Environment(loader=PackageLoader('catena', 'templates'),
                            autoescape=['.j2'],
                            undefined=StrictUndefined,
                            trim_blocks=True,
                            lstrip_blocks=True
                            )

    @classproperty
    def name(cls):
        name = cls.__doc__
        if not name:
            raise AttributeError('{} has no docstring'.format(cls.__name__))
        return name.strip()
    

    def execute(self, **kwargs):
        """
        Execute rendered script

        ** currently only setup for Python scripts ** not finished
        """
        if self.cmd_line_args :
            # local_vars is expected to be dict
            local_vars = self.cmd_line_args
        else:
            local_vars = None
        
        try:
            with DirectorySandbox(self.path):
                script = self.render(**kwargs)
                _execfile(script, locals=local_vars)
        
        except SystemExit as v:
            if v.args and v.args[0]:
                raise
            # Normal exit, just return


    def render(self, **kwargs):
        """
        Render script code object to string
        """
        template = self.jinja_env.get_template(f"{self.id}.j2")
        return template.render(**kwargs)
    
    
    def write(self, target, **kwargs):
        """
        Write script code object to file
        """
        mask = current_umask()
        script = self.render(**kwargs)
        
        with open(f"{target}", 'w') as out:
            out.write(script)
        chmod(target, cls.permissions - mask)        


class JobScript(VirtualScript):
    """
    Generic script of any language
    """
    id: str = 'generic_script'
    permissions = 0o755

    def __init__(self, 
                 path: str,
                 pyflake: Optional[bool] = True,
                 job_script_args: Optional[List[str]] = None,
                 command: Optional[str] = None
                 ):

        # checke if path exists here and if abs path etc.
        self.path = path
        self.posix_path = pathlib.Path(self.path)
        self.pyflake = pyflake
        self.job_script_args = job_script_args
        self.__cmd = command


        # determine job_script file type (charset)
        ftype_raw = os.popen(f'file -bi {self.path}').read()
        self.charset = ftype_raw.split('charset=')[-1].strip('\n')

        # set language map
        self.language_map = lang_extensions._map

        # get job script extension
        self.extension = self.posix_path.suffix
      
        if self.charset == 'binary':
            self.lang = 'binary'

        # else determine language name from langmap
        else:
            self.lang_obj = next((obj for obj in self.language_map if 
                                self.extension in obj['extensions'] or
                                self.extension.lstrip('.') == obj['name']), None)

            # language name
            self.lang = self.lang_obj['name']

        self.__exceptions = [
                             'Matlab',
                             'R',
                             'Stata',
                             'binary'
                            ]


    def __enter__(self):
        return self


    def __exit__( self, exc_type, exc_val, exc_tb ):
        pass


    @property
    def shebang(self):
        # default to shell script
        bash = "#!/bin/bash"
        
        if self.lang in self.__exceptions:
            if self.lang =='R':
                return '#!/usr/bin/env Rscript'
            else:
                return bash
    
        else:
            return f"#!/usr/bin/env {self.lang.lower()}"

    @property
    def run_as_exe(self):

        if (self.__cmd is not None or 
            self.job_script_args is not None):
            return True
        else:
            return False


    @property
    def command(self):
        if self.run_as_exe:
            if self.lang == 'R':
                return 'Rscript'
            elif self.lang == 'binary':
                if self.__cmd is not None:
                    return str(self.__cmd)
                else:
                    return None
            else:
                if self.__cmd is not None:
                    return str(self.__cmd)
                else:
                    return str(self.lang).lower()
        else:
            return None

            
    @property
    def filename(self):
        return self.posix_path.name
        

    @property
    def script(self):

        # check whether context has been set internally
        # if not set context to current working directory
        _context = env.CONTEXT_ROOT
        if not _context:
            _context = os.getcwd()

        with set_context(_context):

            # set script path to absolute path
            if self.posix_path.is_absolute():
                pass
            else:
                self.path = self.posix_path.absolute()
            
            env.JOB_SCRIPT_ABSPATH = self.path

            if self.posix_path.is_file() and self.lang == 'binary':
                content = None

            elif self.posix_path.is_file() and '.py' in self.posix_path.suffix:
                if self.pyflake:
                    flaked = _read_code(str(self.path))
                    head, content = flaked.split('\n', 1)

                    if "#!/" in head:
                        pass
                    else:
                        content = flaked
                
                else:
                    f = open(str(self.path), 'r')
                    code = f.read()

                    if any(l.startswith("#!") for l in code.split("\n")):
                        head, content = code.split('\n', 1)

                    else:
                        content = code

            elif self.posix_path.is_file():
                    f = open(str(self.path), 'r')
                    code = str(f.read())

                    if self.lang == 'binary':
                        content = None
                 
                    elif any(l.startswith("#!") for l in code.split("\n")):
                        head, content = code.split('\n', 1)

                    else:
                        content = code

            else:
                raise FileNotFoundError('job_script does not exists as specified path: ', self.path)

        return self.render(shebang=self.shebang, 
                            lang=self.lang, 
                            script_path=self.path,
                            content=content,
                            script_args=self.job_script_args,
                            command=self.command,
                            run_as_exe=self.run_as_exe)