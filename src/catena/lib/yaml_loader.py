from ruamel import yaml
import os

def safe_loader(stream, Loader=yaml.SafeLoader, master=None):
    loader = Loader(stream)

    if master is not None:
        loader.anchors = master.anchors
    try:
        data = loader.get_single_data()

        return data
    finally:
        loader.dispose()


class Loader(yaml.SafeLoader):

    def __init__(self, stream, preserver_quotes=True):

        self.__stream = stream
        self._root = os.path.split(stream.name)[0]
        super(Loader, self).__init__(stream)
    

    def compose_document(self):
        """Custom composer to overload yaml.SafeLoader.compose_document"""
        self.get_event()
        node = self.compose_node(None, None)
        self.get_event()
        return node

    
    def include(self, node):
        """Include data from external yaml files using constructor"""
        filename = os.path.join(self._root, self.construct_scalar(node))
        with open(filename, 'r') as f:
            return [x for y in list(safe_loader(f, master=self).values()) for x in y]