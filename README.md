# Hot Shelve

## Basic Usages

```python
# hot_shelve provides `HotShelve` and `FlatShelve` classes.
# but currently (v0.1.0) only `FlatShelve` is available.
from hot_shelve import FlatShelve

# open a database
# ===============
# a database is a file with extension `.db`.
db = FlatShelve('path/to/db.db')

# add a immutable key-value pair
# ==============================
db['name'] = 'Bob'

# add a mutable key-value pair
# ============================
db['info'] = {'address': 'Tokyo'}
db['info']['phone_number'] = ['123-456-7890']

# print
# =====
# there are two ways to show its dict structure.
# 1. `db.to_dict()` shows user-oriented dict.
# 2. `db.to_internal_dict()` shows the real internal dict.
# ps: don't use `dict(db)`, it exposes mutable nodes with delegates, you can 
#   not see it clearly like `db.to_dict` does.
print(db.to_dict())
# -> {'name': 'Bob', 
#     'info': {'address': 'Tokyo', 
#              'phone_number': ['123-456-7890']}}
print(db.to_internal_dict())
# -> {'name': 'Bob', 
#     'info.address': 'Tokyo',
#     'info.phone_number': ['123-456-7890']}

# delete a key
# ============
db.pop('name')  # -> 'Bob'
db['info'].pop('address')  # -> 'Tokyo'
print(db.to_dict())
# -> {'info': {'phone_number': ['123-456-7890']}}

# update a key
# ============
db['info']['phone_number'].append('987-654-3210')
print(db.to_dict())
# -> {'info': {'phone_number': ['123-456-7890', 
#                               '987-654-3210']}}

# don't forget sync to disk
# =========================
db.sync()  # now it's safely saved.

# you can do whatever like a Shelve object does
# =============================================
# get, keys, values, items, setdefault, pop, update, clear, sync, close, etc.
for k, v in db.items():
    print(k, v)  # -> 'info', {'phone_number': ['123-456-7890', '987-654-3210']}
    
db.setdefault('name', 'Alice')  # -> 'Alice'
print(db.to_dict())
# -> {'name': 'Alice',
#     'info': {'phone_number': ['123-456-7890', 
#                               '987-654-3210']}}

db.clear()  # -> {}

...

```

## Advanced Usages

```python
from hot_shelve import FlatShelve

db = FlatShelve('path/to/db.db')

db['info'] = {'address': 'Tokyo'}

# use `db['a.b.c']` instead of `db['a']['b']['c']`
db['info.phone_number'] = ['123-456-7890']
#   it has the same effect as `db['info']['phone_number'] = ['123-456-7890']`.
```

## Tricks

1. Use `db['a.b.c']` is better than `db['a']['b']['c']` (they have the same effect but little different performance).
2. *TODO:More*
