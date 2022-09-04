from pydeps.target import Target
from pydeps.dummymodule import (is_module,
                                is_pysource,
                                fname2modname, 
                                python_sources_below)

from dill.source import getsource 

def func_to_string(func):
    """
    Convert a function to it's string representation.
    Nice for writing functions to temporary files.

    works like:

    def myfunction(x):
        '''This is my function docstring'''
        print(x)
   

    func = myfunction
    print(func_to_string(func))
    """
    return getsource(func)
    

# class VirtualFunction(Target):
#
#    def __init__(self,
#                 ):
#
#    super().__init__()


class DummyModule(object):
    """
    Create a file that imports the module to be investigated.
    Adapted from PyPi pydeps (removed cli calls as they were
    causing issues for VirtualSpec)
    """
    def __init__(self, target, **args):
        self._legal_mnames = {}
        self.target = target
        self.fname = '/_dummy_' + garget.modpath.replace('.', '_') + '.py'
        self.absname = os.path.join(target.tempdir, self.fname)

        if target.is_module:
            with open(self.fname, 'w') as fp:
                for fname in python_sources_below(target.package_root):
                    modname = fname2modname(fname, target.syspath_dir)
                    self.print_import(fp, modname)

        elif target.is_dir:
            # FIXME?: not sure what the intended semantics was here, as it is
            #         this will almost certainly not do the right thing...
            with open(self.fname, 'w') as fp:
                for fname in os.listdir(target.dirname):
                    if is_pysource(fname):
                        self.print_import(fp, fname2modname(fname, ''))

        else:
            assert target.is_pysource
            with open(self.fname, 'w') as fp:
                self.print_import(fp, target.modpath)

    def text(self):
        """Return the content of the dummy module.
        """
        return open(self.fname).read()

    def legal_module_name(self, name):
        """Legal module names are dotted strings where each part
           is a valid Python identifier.
           (and not a keyword, and support unicode identifiers in
           Python3, ..)
        """
        if name in self._legal_mnames:
            return self._legal_mnames[name]

        for part in name.split('.'):
            try:
                exec("%s = 42" % part, {}, {})
            except:  # pragma: nocover
                self._legal_mnames[name] = False
                return False
        self._legal_mnames[name] = True
        return True

    def print_header(self, fp):  # pragma: nocover
        # we're not executing the file in fp, so really not necessary to
        # catch import errors
        print(textwrap.dedent("""
            import sys
            import traceback        
        """), file=fp)

    def print_import(self, fp, module):
        if not self.legal_module_name(module):
            #log.warning("SKIPPING ILLEGAL MODULE_NAME: %s", module)
            return

        mparts = module.rsplit('.', 1)
        # we're not executing the file in fp, so really not necessary to
        # catch import errors
        if len(mparts) == 1:
            print(textwrap.dedent("""\
                import {module}
            """).format(module=module), file=fp)
        else:
            print(textwrap.dedent("""\
                from {prefix} import {mname}
            """).format(prefix=mparts[0], mname=mparts[1]), file=fp)

    
