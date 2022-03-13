import shelve


class FlatShelve(shelve.DbfilenameShelf):
    
    def __init__(self, file: str):
        if file.endswith('.db'): file = file[:-3]
        super().__init__(file, writeback=False)
        self._key_map = {}  # dict[str, dict[str, dict[str, ...] | None] | None]
    
    def __setitem__(self, key, value):
        key_chain = []
        
        def recurse(key: str, val, key_map: dict):
            key_chain.append(key)
            
            if isinstance(val, dict):
                for k, v in val.items():
                    recurse(k, v, key_map.setdefault(k, {}))
            elif isinstance(val, (list, set)):
                for i, v in enumerate(val):
                    k = f'#{i}'
                    recurse(k, v, key_map.setdefault(k, {}))
            else:
                flat_key = '.'.join(key_chain)
                super().__setitem__(flat_key, val)
                key_map[key] = None
            
            key_chain.pop()
            
        recurse(key, value, self._key_map)
        
    @staticmethod
    def _is_mutable(value):
        return isinstance(value, (dict, list, set))
