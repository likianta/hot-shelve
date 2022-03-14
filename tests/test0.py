import os

from lk_logger import lk

from hot_shelve import FlatShelve

# clear db files
# for f in os.listdir('test_db'):
#     if f.startswith('.'):
#         continue
#     os.remove(f'test_db/{f}')
#     lk.loga(f'removed file: test_db/{f}')

db = FlatShelve('test_db/test0.db')
lk.loga(db.to_dict())
lk.loga(db.to_internal_dict())
db['name'] = 'Bob'
db['auth'] = {'password': '1234'}
db.sync()
lk.loga(db._key_map)  # noqa
lk.loga(db.to_dict())
lk.loga(db.to_internal_dict())
lk.loga(db['auth'])
lk.loga(db['auth']['password'])
db['auth']['password'] = '4321'
lk.loga(db['auth'])
lk.loga(db['auth']['password'])
db.sync()
db.close()
