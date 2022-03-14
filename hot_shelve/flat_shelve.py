import json
import shelve
from os.path import exists
from typing import Any
from typing import Iterator
from typing import TextIO
from typing import Union


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
    _file_map_handle: TextIO
    
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
            with open(self._file_map) as f:
                self._key_map = json.load(f)
        else:
            self._key_map = {}
        self._file_map_handle = open(self._file_map, 'w')
    
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
        
        parent_node = node
        parent_key_chain = key_chain
        node = node[key]
        key_chain = key_chain + [key]
        flat_key = '.'.join(key_chain)
        
        if type(node) is dict:
            return DictNode(self, node, key_chain, node)
        elif node[0] == 0:
            return self._flat_db[flat_key]
        else:
            real_value = self._flat_db[flat_key]
            return (
                ListNode(self, parent_node, parent_key_chain, key, real_value)
                if node[1] is list else
                SetNode(self, parent_node, parent_key_chain, key, real_value)
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
                yield DictNode(self, value, key_chain + [key], value)
            elif value[0] == 0:
                flat_key = '.'.join(key_chain + [key])
                yield self._flat_db[flat_key]
            else:
                flat_key = '.'.join(key_chain + [key])
                real_value = self._flat_db[flat_key]
                yield (
                    ListNode(self, node, key_chain, key, real_value)
                    if value[1] is list else
                    SetNode(self, node, key_chain, key, real_value)
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
        json.dump(self._key_map, self._file_map_handle)
    
    def clear(self):
        self._flat_db.clear()
        self._key_map.clear()
    
    def close(self):
        self._flat_db.close()
        json.dump(self._key_map, self._file_map_handle)
        self._file_map_handle.close()


# -----------------------------------------------------------------------------

class MutableNode:
    
    def __init__(self,
                 root: FlatShelve,
                 node: T.Node,
                 key_chain: T.KeyChain,
                 mutable: T.Mutable):
        self._root = root
        self._node = node
        self._key_chain = key_chain
        self._value = mutable


# noinspection PyProtectedMember
class DictNode(MutableNode):
    """ dict-like object.
    
    note: in DictNode, `self._value` is same as `self._node`. we prefer to use
        `self._node` to avoid confusion.
    """
    
    # (sort methods by alphabetical order.)
    
    def __contains__(self, key):
        return key in self._node
    
    def __getitem__(self, key):
        return self._root._get_node(
            self._node, self._key_chain,
            key, default=KeyError
        )
    
    def __iter__(self):
        return iter(self._node)
    
    def __len__(self):
        return len(self._node)
    
    def __setitem__(self, key, value):
        self._root._set_node(self._node, self._key_chain, key, value)
    
    def __str__(self):
        return str(self._root._instantiate(self._node, self._key_chain))
    
    def clear(self):
        self._node.clear()
        self._root.pop('.'.join(self._key_chain))
    
    def get(self, key, default=None):
        return self._root._get_node(self._node, self._key_chain, key, default)
    
    def items(self):
        return self._root._node_items(self._node, self._key_chain)
    
    def keys(self):
        return self._root._node_keys(self._node)
    
    def pop(self, key, default=None):
        return self._root._pop_node(self._node, self._key_chain, key, default)
    
    def popitem(self):
        key, _ = self._node.popitem()
        self._node[key] = (0, None)
        return key, self.pop(key)
    
    def setdefault(self, key, default=None):
        if key in self._node:
            return self[key]
        else:
            self[key] = default
            return self[key]
    
    def update(self, other: dict):
        for k, v in other.items():
            self[k] = v
    
    def values(self):
        return self._root._node_values(self._node, self._key_chain)


# noinspection PyProtectedMember
class ListNode(MutableNode):
    _value: list
    
    def __init__(self,
                 root: FlatShelve,
                 parent_node: T.Node,
                 parent_key_chain: T.KeyChain,
                 current_key: T.Key,
                 mutable: T.Mutable):
        super().__init__(root, parent_node, parent_key_chain, mutable)
        self._current_key = current_key
    
    def append(self, value):
        self._value.append(value)
        self._refresh_root()
    
    def clear(self):
        self._value.clear()
        self._refresh_root()
    
    def copy(self):
        return self._value.copy()
    
    def count(self, value):
        return self._value.count(value)
    
    def extend(self, iterable):
        self._value.extend(iterable)
        self._refresh_root()
    
    def index(self, value, start=0, stop=None):
        return self._value.index(value, start, stop)
    
    def insert(self, index: int, value):
        self._value.insert(index, value)
        self._refresh_root()
    
    def pop(self, index=-1):
        value = self._value.pop(index)
        self._refresh_root()
        return value
    
    def remove(self, value):
        self._value.remove(value)
        self._refresh_root()
    
    def reverse(self):
        self._value.reverse()
        self._refresh_root()
    
    def sort(self, key=None, reverse=False):
        self._value.sort(key=key, reverse=reverse)
        self._refresh_root()
    
    def _refresh_root(self):
        self._root._set_node(
            self._node, self._key_chain,
            self._current_key, self._value
        )


# noinspection PyProtectedMember
class SetNode(MutableNode):
    _value: set
    
    def __init__(self,
                 root: FlatShelve,
                 parent_node: T.Node,
                 parent_key_chain: T.KeyChain,
                 current_key: T.Key,
                 mutable: T.Mutable):
        super().__init__(root, parent_node, parent_key_chain, mutable)
        self._current_key = current_key
    
    def add(self, value):
        self._value.add(value)
        self._refresh_root()
    
    def clear(self):
        self._value.clear()
        self._refresh_root()
    
    def copy(self):
        return self._value.copy()
    
    def difference(self, *args):
        return self._value.difference(*args)
    
    def difference_update(self, *args):
        self._value.difference_update(*args)
        self._refresh_root()
    
    def discard(self, value):
        self._value.discard(value)
        self._refresh_root()
    
    def intersection(self, *args):
        return self._value.intersection(*args)
    
    def intersection_update(self, *args):
        self._value.intersection_update(*args)
        self._refresh_root()
    
    def isdisjoint(self, other):
        return self._value.isdisjoint(other)
    
    def issubset(self, other):
        return self._value.issubset(other)
    
    def issuperset(self, other):
        return self._value.issuperset(other)
    
    def pop(self):
        value = self._value.pop()
        self._refresh_root()
        return value
    
    def remove(self, value):
        self._value.remove(value)
        self._refresh_root()
    
    def symmetric_difference(self, other):
        self._value.symmetric_difference(other)
        self._refresh_root()
    
    def symmetric_difference_update(self, other):
        self._value.symmetric_difference_update(other)
        self._refresh_root()
    
    def union(self, *args):
        return self._value.union(*args)
    
    def update(self, *args):
        self._value.update(*args)
        self._refresh_root()
    
    def _refresh_root(self):
        self._root._set_node(
            self._node, self._key_chain,
            self._current_key, self._value
        )
