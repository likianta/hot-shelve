import lk_logger
lk_logger.setup(show_varnames=True)

from hot_shelve import FlatShelve


def _random_create_db() -> FlatShelve:
    from uuid import uuid1
    return FlatShelve(f'test_db/{uuid1()}.db')


def test_classic():
    db = _random_create_db()
    print(db.to_dict())
    print(db.to_internal_dict())
    db['name'] = 'Bob'
    db['auth'] = {'password': '1234'}
    db.sync()
    print(db.key_map)  # noqa
    print(db.to_dict())
    print(db.to_internal_dict(), ':l')
    print(db['auth'])
    print(db['auth']['password'])
    db['auth']['password'] = '4321'
    print(db['auth'])
    print(db['auth']['password'])
    db.sync()
    db.close()


def test_set_dict_item():
    db = _random_create_db()
    print(db.to_dict())
    db['a.a'] = {
        'b': 1,
    }
    print(db.to_dict())
