from . import modulecmd as modulecmd
from .scripts import _read_code
from . import env as env
import pathlib
import jinja2
from jinja2 import Environment, PackageLoader, select_autoescape, StrictUndefined

import os
from pathlib import Path
import sys
from typing import Optional
from rich import print
from rich.filesize import decimal
from rich.markup import escape
from rich.text import Text
from rich.tree import Tree

def find_virtual_script(kind='Generic'):
    """
    Return base license class
    Args:
        license(str): name of license file (Apache2, BSD3, MIT)
    
    ** need to fix **
    """
    specname = str(pathlib.Path('.').parent.resolve().parent.absolute().parts[-1])
    return get_module('script', modpath=f'{specname}.lib', mod=f'{kind}ScriptClass')


def virtual_script(filename, content, shebang="#!/bin/bash", kind='Generic', outdir=None):
    """
    Renders virtual script to string
    
    Args:
        filename(str): name of file (script) that was read in (virtualized)
        content(str): content of script as string
        shebang(str): shebang to place at top of virtual sript
        kind(str): type of virtual script class
        outdir(str): directory to write script to file. If none, does not write anything to file

    ** need to fix **
    """

    # get script class
    script = find_virtual_script(kind)
    script = getattr(script, f'{kind}Script')
    
    # renders script from jinja2 template
    rendered_script = script.render(name=author, email=email)

    # write to file if outdir != None
    if outdir is not None:
        script.write(filename=filename, content=content, shebang=shebang, kind=kind, path=outdir)

    return rendered_script



def format_cmd_name(python_name):
    """Convert module name (with ``_``) to command name (with ``-``)."""
    return python_name.replace('_', '-')

def python_name(cmd_name):
    """Convert ``-`` to ``_`` in command name, to make a valid identifier."""
    return cmd_name.replace("-", "_")


def get_module(cmd_name, modpath=__name__, mod=None):
    """
    Imports the module for a porticular command name and returns it
    
    Args:
        cmd_name (str): name of the command for which to get the module
              (python modules contain ``_``, not ``-`` like spack commands do)
        from_list_ (list [str]): list of functions to import from top level class
    Adapted from spack.cmd
    """
    pname = python_name(cmd_name)
    if mod is None:
        mod = pname

    try:
        # Try to import the command from the built-in directory
        module_name = "{}.{}".format(modpath, pname)
        module = __import__(module_name,
                            fromlist=[pname, mod],
                            level=0)
    except Exception as err:
        print(err)
        #logger.exception("{} | No module found for command: {} |".format(err, cmd_name))
        return False 
    
    return module


class ContextTree:

    def __init__(self, root: Optional[str]=None):

        if root is None:
            _root = env.CONTEXT_ROOT
            if not _root:
                self.root = os.getcwd()
            else:
                self.root = env.CONTEXT_ROOT
        
        self.posix_path = Path(self.root)
    

    def walk_directory(self, directory: pathlib.Path, tree: Tree) -> None:
        """Recursively build a Tree with directory contents."""
        # Sort dirs first then by filename
        paths = sorted(
            Path(directory).iterdir(),
            key=lambda path: (path.is_file(), path.name.lower()),
        )
        for path in paths:
            # Remove hidden files
            if path.name.startswith("."):
                continue
            if path.is_dir():
                style = "dim" if path.name.startswith("__") else ""
                branch = tree.add(
                    f"[bold magenta]:open_file_folder: [link file://{path}]{escape(path.name)}",
                    style=style,
                    guide_style=style,
                )
                self.walk_directory(path, branch)
            else:
                text_filename = Text(path.name, "green")
                text_filename.highlight_regex(r"\..*$", "bold red")
                text_filename.stylize(f"link file://{path}")
                file_size = path.stat().st_size
                text_filename.append(f" ({decimal(file_size)})", "blue")
                icon = "🐍 " if path.suffix == ".py" else "📄 "
                tree.add(Text(icon) + text_filename)
    
    @classmethod
    def render(cls, root: Optional[str] = None):

        cxt_tree = cls(root=root)

        directory = cxt_tree.posix_path.absolute()

        if cxt_tree.posix_path.is_dir():
            tree = Tree(
                        f":open_file_folder: [link file://{directory}]{directory}",
                        guide_style="bold bright_blue",
                       )
            cxt_tree.walk_directory(cxt_tree.posix_path, tree)
            print(tree)
        