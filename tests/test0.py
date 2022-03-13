from lk_logger import lk

from hot_shelve import FlatShelve

db = FlatShelve('test_db/test7.db')
lk.loga(dict(db))
db['name'] = 'Bob'
db['auth'] = {'password': '1234'}
lk.loga(db._key_map)
lk.loga(db['auth'])
lk.loga(db['auth']['password'])
db['auth']['password'] = '4321'
lk.loga(db['auth'])
lk.loga(db['auth']['password'])
db.sync()
db.close()
