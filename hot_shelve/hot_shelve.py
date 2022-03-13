import os
import shelve


class HotShelve:
    # see `_init_hot_dict` for details.
    _hot_key_chain: list[str]
    _hot_lvl_chain: list[str]
    _hot_map: dict[str, shelve.Shelf]
    
    def __init__(self, db_path: str, base_dict: dict):
        """
        args:
            db_path:
                give a **directory** path.
                the path can either be existed or not.
            base_dict:
                a normal python dict, but with special keys:
                    if you want to mark some key as 'hot', use 'hot:' prefix.
                    for example:
                        {'hot:key1': 'value1', 'key2': 'value2', ...}
                    if you want to mark some key dynamic, use 'any:' previx.
                    for example:
                        {'any:key1': 'value1', 'key2': 'value2', ...}
                be noticed, once the base_dict is given, its structure cannot
                be changed. i.e. you can't use `clear`, `pop`, `popitem` to the
                dict.
                additional noted:
                    - a hot key cannot be a var key in the same time.
                    - do not use '.' in your real keys. this conflicts with
                      `self.__getattr__ : (arg) key_chain` format.
        """
        if os.path.exists(db_path): assert os.path.isdir(db_path)
        else: os.mkdir(db_path)
        self._init_hot_dict(db_path, base_dict)
        
    def _init_hot_dict(self, db_path: str, base_dict: dict) -> None:
        """
        if a key is marked as 'hot', it will be saved in a separated file
        space. for example:
            base_dict = {
                'any:user_id': {
                    'name': 'some_user',
                    'created': '2022-01-01',
                    'hot:updated': '2022-01-01',
                }
            }
        HotShelve takes care of how to sync `status` data with the minimal
        effort (the least required changes) to local database:
            database:
            |= <db_path>
                |- 0.db
                |   ~ {
                |   ~     '2q3Vmk': {
                |   ~         'name': 'some_user',
                |   ~         'created': '2022-01-01',
                |   ~         'updated': '#2q3Vmk'
                |   ~ }
                |- 1.db
                |   ~ {
                |   ~     '2q3Vmk': '2022-01-01'
                |   ~ }
        
        return:
            e.g. {
                '0-root': shelve.Shelve,
                '1-updated': shelve.Shelve,
            }
        """
        hot_db = {}
        hot_keys = {}
        tmp_key_chain = []
        simple_counter = 0
        
        def detect_hot_nodes_1(node: dict):
            """ gradually build  `hot_db`. """
            nonlocal simple_counter
            
            for k, v in node.items():
                if k.startswith('any:'):
                    # assert isinstance(v, dict)
                    tmp_key_chain.append('*')
                    
                elif k.startswith('hot:'):
                    # assert isinstance(v, dict)
                    tmp_key_chain.append(k[4:])
                    hot_key_chain = '.'.join(tmp_key_chain)
                    
                    simple_counter += 1
                    file_name = str(simple_counter) + '.db'
                    file_path = db_path + '/' + file_name
                    
                    hot_db[hot_key_chain] = shelve.open(file_path[:-3])
                    #   ...[:-3]: remove '.db' suffix, because `shelve.open`
                    #       will add it implicitly.
            
                if isinstance(v, dict):
                    detect_hot_nodes_1(v)
                
                tmp_key_chain.pop()
        
        detect_hot_nodes_1(base_dict)  # after this, `hot_db` is filled.
        assert not tmp_key_chain
        print('built {} hot nodes.'.format(simple_counter))
        del simple_counter, tmp_key_chain
        
        def detect_hot_nodes_2(node_s: dict, node_t: dict) -> bool:
            """ gradually build  `hot_keys`. """
            # tmp_node = {}  # to be merged with `node_t`.
            has_hot_node = False
            
            for k, v in node_s.items():
                if k.startswith('hot:'):
                    has_hot_node = True
                    node_t[k[4:]] = {}
                    continue
                if isinstance(v, dict):
                    if k.startswith('any:'): k = '*'
                    sub_node_t = node_t[k] = {}
                    if detect_hot_nodes_2(v, sub_node_t):
                        return True
            else:
                return False
        
        print(self._hot_key_chain, self._hot_lvl_chain, self._hot_map)
        
    def __getitem__(self, key_chain: str):
        """
        args:
            key_chain: e.g. '2q3Vmk.name'
        """
        for key in key_chain.split('.'):
            pass
