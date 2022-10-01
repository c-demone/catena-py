from concurrent.futures import ProcessPoolExecutor # best for cpu intensive
from concurrent.futures import ThreadPoolExecutor # beter for i/o intensive
from findimports import find_imports






def get_imports(filepath):
    """
    Get list of ImportInfo objects for imports in a given
    python file.

    Atr of ImportInfo:
        self.name
        self.filename
        self.lineno
        self.level
    
    """
    import_info = find_imports(filepath)

    imports = [i.name for i import import_info]
    return imports


class Result:

    def __init__(self,
                 future):

        while not future.done():
            time.sleep(2)

        self.result = future.result()


class SLURMCallback:

    def __init__(self, f, target, mode='procs', workers=1):
        self.callback = f
        self.target = target
        self.workers = workers
        self.mode = mode


    def run(self, *args): # mode also threads

        if self.mode == 'procs':
            self.execute_proc_pool(args)
        
        if self.mode == 'threads':
            self.execute_thread_pool(args)


    def execute_proc_pool(self, args):
        self.pool = ProcessPoolExecutor(self.workers)
        # validate that args are picklable and that callback is picklable
        # if not then use ThreadPoolExecutor
        self.future = self.pool.submit(self.callback, *args)
        return self.future
    

    def execute_thread_pool(self, args):
        self.pool = ThreadPoolExecutor(self.workers)
        self.future = self.pool.submit(self.callback, *args)
        return self.future

    def pickle_rick(self):
        
        self.holder = Result(self.future)
        with open(self.target.pickle_path, 'wb') as f:
            pickle.dump(result, f)

        self.result = self.holder.result()

    def unpickle_rick(self):
        
        with open(self.target.pickle_path, 'wb') as f:
            self.holder = pickle.load(f)

        self.result = self.holder.result()

