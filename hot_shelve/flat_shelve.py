import builtins
import json
import shelve
from os.path import exists
from typing import Any
from typing import Iterator
from typing import Union

# to avoid `NameError: name 'open' is not defined` when calling
# `FlatShelve.close`.
_open = builtins.open


class T:
    Key = str  # e.g. 'a'
    FlatKey = str  # e.g. 'a.b.c'
    Value = Any
    
    Node = dict[Key, Value]
    KeyChain = list[Key]
    #   KeyChain should be always sync with the level of Node.
    #   flat_key = '.'.join(key_chain)
    
    Mutable = Union[dict, list, set]
    Immutable = Union[bool, bytes, int, float, str, tuple, None]


class FlatShelve:
    _file: str
    _file_map: str
    _flat_db: shelve.Shelf
    _key_map: dict
    ''' type: dict[str, dict a | tuple b]
            a: the same structure like root dict. (dict[str, dict[...] | tuple])
            b: tuple[int, type]
                int: enum[0, 1]
                    0 for immutable, 1 for mutable.
                type: union[immutable, mutable]
                    immutable: union[bool, float, int, str, tuple, None]
                    mutable: union[dict, list, set]
                warning: currently, if you have a class, instance etc., it will
                    be treated as immutable.
    '''
    
    def __init__(self, file: str):
        assert file.endswith('.db')
        self._file = file
        self._file_map = file[:-3] + '.map.db'
        
        self._flat_db = shelve.open(self._file)
        if exists(self._file_map):
            with _open(self._file_map) as f:
                self._key_map = json.load(f)
        else:
            self._key_map = {}
    
    # -------------------------------------------------------------------------
    # dict-like behaviors
    
    def __setitem__(self, key: str, value) -> None:
        previous_key, current_key = self._rsplit_key(key)
        node, key_chain = self._locate_node(previous_key)
        self._set_node(node, key_chain, current_key, value)
    
    def __getitem__(self, key: str):
        previous_key, current_key = self._rsplit_key(key)
        node, key_chain = self._locate_node(previous_key)
        return self._get_node(node, key_chain, current_key, default=KeyError)
    
    def keys(self):
        return self._node_keys(self._key_map)
    
    def values(self):
        return self._node_values(self._key_map, [])
    
    def items(self):
        return self._node_items(self._key_map, [])
    
    def get(self, key: str, default=None):
        if key in self._flat_db:
            flat_key = key
            return self._flat_db[flat_key]
        
        previous_key, current_key = self._rsplit_key(key)
        node, key_chain = self._locate_node(previous_key)
        assert type(node) is dict
        return self._get_node(node, key_chain, current_key, default)
    
    def setdefault(self, key: str, default=None):
        previous_key, current_key = self._rsplit_key(key)
        node, key_chain = self._locate_node(previous_key)
        assert type(node) is dict
        
        if current_key in node:
            return self._get_node(node, key_chain, current_key)
        else:
            self._set_node(node, key_chain, current_key, default)
            return self._get_node(node, key_chain, current_key)
    
    # noinspection PyMethodOverriding
    def update(self, other: dict):
        for key, value in other.items():
            self[key] = value
    
    def pop(self, key: str, default=None):
        previous_key, current_key = self._rsplit_key(key)
        node, key_chain = self._locate_node(previous_key)
        assert type(node) is dict
        return self._pop_node(node, key_chain, current_key, default)
    
    def popitem(self):
        key, _ = self._key_map.popitem()
        self._key_map[key] = (0, None)
        #   workaround to prevent the key missing in `self.pop` method.
        return key, self.pop(key)
    
    # -------------------------------------------------------------------------
    # dict-like behaviors (magic methods)
    
    def __iter__(self):
        return iter(self._key_map)
    
    def __len__(self):
        return len(self._key_map)
    
    def __str__(self):
        return str(self._instantiate(self._key_map, []))
    
    def __contains__(self, key: str) -> bool:
        if '.' in key:
            if key in self._flat_db:
                return True
            previous_key, current_key = key.rsplit('.', 1)
            node, _ = self._locate_node(previous_key)
            assert type(node) is dict
            return current_key in node
        else:
            return key in self._key_map
    
    # -------------------------------------------------------------------------
    # advanced methods (node based operations)
    
    def _set_node(self, node: T.Node, key_chain: T.KeyChain,
                  key: T.Key, value: T.Value):
        # print('[D2429]', node, key_chain, key, value)
        
        if key in node:
            for flat_key in self._collect_flat_keys(node, key_chain, key):
                # print('[D1433]', 'found existed flat key, pop it',
                #       key, flat_key)
                self._flat_db.pop(flat_key)
            node.pop(key)
            
        def recurse(node: T.Node, key: T.Key, value: T.Value):
            if isinstance(value, dict):
                next_node = node[key] = {}
                key_chain.append(key)  # temporarily sync with `next_node`.
                for k, v in value.items():
                    recurse(next_node, k, v)
                key_chain.pop()  # restore sync with `node`.
            
            else:
                if isinstance(value, (list, set)):
                    node[key] = (1, type(value))
                else:
                    # # node[key] = (0, type(value))
                    node[key] = (0, None)
                    #   TODO: no need to store the immutable type in current
                    #       version.
                flat_key = '.'.join(key_chain + [key])
                # print('[D5809]', flat_key, value)
                self._flat_db[flat_key] = value
        
        recurse(node, key, value)
    
    def _get_node(self, node: T.Node, key_chain: T.KeyChain,
                  key: T.Key, default=None):
        key_chain = key_chain.copy()
        
        if default is not KeyError and key not in node:
            return default
        
        node = node[key]
        key_chain.append(key)
        flat_key = '.'.join(key_chain)
        
        if type(node) is dict:
            return DictNode(self, flat_key, node)
        elif node[0] == 0:
            return self._flat_db[flat_key]
        else:
            return (
                ListNode(self, flat_key, node[1]) if node[1] is list else
                SetNode(self, flat_key, node[1])
            )
    
    def _pop_node(self, node: T.Node, key_chain: T.KeyChain,
                  key: T.Key, default=None):
        if key not in node:
            return default
        out = self._instantiate(node[key], key_chain + [key])
        for flat_key in self._collect_flat_keys(node, key_chain, key):
            self._flat_db.pop(flat_key)
        node.pop(key)
        return out
    
    # noinspection PyMethodMayBeStatic
    def _node_keys(self, node: T.Node):
        return node.keys()
    
    def _node_values(self, node: T.Node, key_chain: T.KeyChain):
        for key, value in node.items():
            if isinstance(value, dict):
                yield DictNode(self, key, value)
            elif value[0] == 0:
                flat_key = '.'.join(key_chain + [key])
                yield self._flat_db[flat_key]
            else:
                yield (
                    ListNode(self, key, value[1]) if value[1] is list else
                    SetNode(self, key, value[1])
                )
    
    def _node_items(self, node: T.Node, key_chain: T.KeyChain):
        return zip(node.keys(), self._node_values(node, key_chain))
    
    def _instantiate(self, node: T.Node, key_chain: T.KeyChain) -> dict | Any:
        
        if type(node) is dict:
            if node:
                out = {}
                
                def recurse(node_s: dict, node_t: dict):
                    for k, v in node_s.items():
                        key_chain.append(k)
                        if type(v) is dict:
                            next_node_t = node_t[k] = {}
                            recurse(v, next_node_t)
                        else:
                            flat_key = '.'.join(key_chain)
                            node_t[k] = self._flat_db[flat_key]
                        key_chain.pop()
                
                recurse(node, out)
                return out
            else:
                return {}
        
        else:
            flat_key = '.'.join(key_chain)
            return self._flat_db[flat_key]
    
    def to_dict(self) -> dict:
        return self._instantiate(self._key_map, [])
    
    def to_internal_dict(self) -> dict:
        return dict(self._flat_db)
    
    @staticmethod
    def _collect_flat_keys(
            node: T.Node, key_chain: T.KeyChain, target_key=None
    ) -> Iterator[T.FlatKey]:
        key_chain = key_chain.copy()
        
        if target_key is not None:
            node = node[target_key]
            key_chain.append(target_key)  # always keep sync with `node`.
            if not isinstance(node, dict):
                yield '.'.join(key_chain)
                return
        
        def recurse(node: dict):
            for k, v in node.items():
                key_chain.append(k)
                if isinstance(v, dict):
                    yield from recurse(v)
                else:
                    yield '.'.join(key_chain)
                key_chain.pop()
        
        yield from recurse(node)
    
    # -------------------------------------------------------------------------
    # frequently used (private) methods
    
    @staticmethod
    def _rsplit_key(key: T.Key) -> tuple[T.Key, T.Key]:
        if '.' in key:
            return key.rsplit('.', 1)  # noqa
        else:
            return '', key
    
    def _locate_node(self, key: T.Key) -> tuple[T.Node, T.KeyChain]:
        if not key:
            return self._key_map, []
        else:
            key_chain = key.split('.')
        node = self._key_map
        for key in key_chain:
            node = node[key]
        return node, key_chain
    
    @staticmethod
    def _is_mutable(value: T.Value) -> bool:
        return isinstance(value, (dict, list, set))
    
    # -------------------------------------------------------------------------
    
    def sync(self):
        self._flat_db.sync()
        # TODO: also sync self._key_map
    
    def clear(self):
        self._flat_db.clear()
        self._key_map.clear()
    
    def close(self):
        self._flat_db.close()
        with _open(self._file_map, 'w') as f:
            json.dump(self._key_map, f)


# -----------------------------------------------------------------------------

class MutableNode:
    
    def __init__(self, root: FlatShelve,
                 flat_key: T.FlatKey,
                 mutable: T.Mutable):
        assert flat_key
        self._root = root
        self._key = flat_key
        self._value = mutable


class DictNode(MutableNode):
    """ dict-like object. """
    
    def __init__(self, root, flat_key, mutable):
        super().__init__(root, flat_key, mutable)
        self._node = self._value
        self._key_chain = self._key.split('.')
    
    def __contains__(self, key):
        return key in self._value
    
    def __getitem__(self, key):
        return self._root[self._key + '.' + key]
    
    def __iter__(self):
        return iter(self._value)
    
    def __len__(self):
        return len(self._value)
    
    def __setitem__(self, key, value):
        # noinspection PyProtectedMember
        self._root._set_node(self._value, self._key_chain, key, value)
        # self._root[self._key + '.' + key] = value
    
    def __str__(self):
        # noinspection PyProtectedMember
        return str(self._root._instantiate(self._value, self._key.split('.')))
    
    def clear(self):
        self._value.clear()
        self._root.pop(self._key)
    
    def get(self, key, default=None):
        return self._root.get(self._key + '.' + key, default)
    
    def items(self):
        # noinspection PyProtectedMember
        return self._root._node_items(self._value, self._key.split('.'))
    
    def keys(self):
        # noinspection PyProtectedMember
        return self._root._node_keys(self._value)
    
    def pop(self, key, default=None):
        return self._root.pop(self._key + '.' + key, default)
    
    def popitem(self):
        key, _ = self._value.popitem()
        self._value[key] = None
        return key, self._root.pop(self._key + '.' + key)
    
    def setdefault(self, key, default=None):
        return self._root.setdefault(self._key + '.' + key, default)
    
    def update(self, other: dict):
        for k, v in other.items():
            self[k] = v
    
    def values(self):
        # noinspection PyProtectedMember
        return self._root._node_values(self._value, self._key.split('.'))


class ListNode(MutableNode):
    _node: list
    pass


class SetNode(MutableNode):
    _node: set
    pass
