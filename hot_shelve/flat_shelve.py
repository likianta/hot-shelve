import builtins
import json
import shelve
from os.path import exists
from lk_logger import lk

# to avoid `NameError: name 'open' is not defined` when calling
# `FlatShelve.close`.
_open = builtins.open


class FlatShelve(shelve.DbfilenameShelf):
    _file: str
    _file_map: str
    _key_map: dict  # dict[str, dict[str, dict[str, ...] | None] | None]
    
    def __init__(self, file: str):
        assert file.endswith('.db')
        self._file = file
        self._file_map = file[:-3] + '.map.db'
        super().__init__(self._file[:-3])
        if exists(self._file_map):
            with _open(self._file_map) as f:
                self._key_map = json.load(f)
        else:
            self._key_map = {}
    
    def __setitem__(self, key: str, value):
        x = key.split('.')
        prefix_key_chain = x[:-1]
        succeeding_key_chain = []
        current_key = x[-1]
        
        node = self._key_map
        for k in prefix_key_chain:
            node = node.setdefault(k, {})

        def recurse_value(key: str, val, node: dict):
            succeeding_key_chain.append(key)
            if isinstance(val, dict):
                node = node.setdefault(key, {})
                for k, v in val.items():
                    recurse_value(k, v, node)
            # elif isinstance(val, (list, set)):
            #     for i, v in enumerate(val):
            #         k = f'#{i}'
            #         recurse(k, v, key_map.setdefault(k, {}))
            else:
                node[key] = None
                flat_key = '.'.join(prefix_key_chain + succeeding_key_chain)
                lk.logt('[D2818]', flat_key, val)
                super(FlatShelve, self).__setitem__(flat_key, val)

            succeeding_key_chain.pop()
        
        recurse_value(current_key, value, node)
    
    def __getitem__(self, key: str):
        node = self._key_map
        for k in key.split('.'):
            node = node[k]
        if node is None:
            return super(FlatShelve, self).__getitem__(key)
        else:
            return Node(self, key)
    
    @staticmethod
    def _is_mutable(value):
        return isinstance(value, (dict, list, set))
    
    def close(self):
        super().close()
        with _open(self._file_map, 'w') as f:
            json.dump(self._key_map, f)


class Node:
    """ dict-like object. """
    
    def __init__(self, root: FlatShelve, flat_key: str):
        self._root = root
        self._key = flat_key
    
    def __setitem__(self, key, value):
        self._root[self._key + '.' + key] = value
    
    def __getitem__(self, key):
        return self._root[self._key + '.' + key]
