# Hot Shelve

A wrapper for Python shelve that supports updating nested dictionaries in a simple way.

Essentially, you don't need this any more:

```python
import shelve
db = shelve.open('some_file.db')
db['key'] = {'a': 1, 'b': 2}
temp = db['key']
temp['c'] = 3
db['key'] = temp
db.sync()
```

To use:

```python
import hot_shelve
db = hot_shelve.FlatShelve('some_file.db')
db['key'] = {'a': 1, 'b': 2}
db['key']['c'] = 3
db.sync()
```

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

Follow the instructions to get a (little) better performance (in theoretical).

1.  `db['a.b.c']` is better than `db['a']['b']['c']`.
    
    ```python
    # good
    db['a']['b']['c'] = 'xxx'
    
    # better
    db['a.b.c'] = 'xxx'
    ```

2.  To frequently update a node, assign it to a new variable.

    ```python
    # good
    db['a']['b']['0'] = '000'
    db['a']['b']['1'] = '111'
    db['a']['b']['2'] = '222'
    ...

    # better
    db['a.b.0'] = '000'
    db['a.b.1'] = '111'
    db['a.b.2'] = '222'
    ...

    # best
    node = db['a.b']
    node['0'] = '000'
    node['1'] = '111'
    node['2'] = '222'
    ...
    ```

## Cautions

-   Do not use '.' in your own key name, the period symbol is reserved for key chain derivation.

    ```
    # wrong
    words_db['splash'] = {
        'e.g.': 'there was a splash, and then silence.'
    }
    ''' it will generate...
        print(words_db.to_dict())
        # -> {'splash': {'e': {'g': {'': 'there was a splash, and then silence.'}}}}
        print(words_db.to_internal_dict())
        # -> {'splash.e.g.': 'there was a splash, and then silence.'}
    '''
    
    # right
    words_db['splash'] = {
        'example': 'there was a splash, and then silence.'
    }
    print(words_db.to_dict())
    # -> {'splash': {'example': 'there was a splash, and then silence.'}}
    print(words_db.to_internal_dict())
    # -> {'splash.example': 'there was a splash, and then silence.'}
    ```

-   The file size will be larger than `shelve.Shelve`, because it uses a flat key-value structure.

    Illustration:

    A normal `Shelve` object:

    ```yaml
    data:
        name: 'Bob'
        info:
            address: 'Tokyo'
            phone_number:
                - 123-456-7890
                - 987-654-3210
    ```

    A `FlatShelve` object:

    ```yaml
    data.name: 'Bob'
    data.info.address: 'Tokyo'
    data.info.phone_number:
        - 123-456-7890
        - 987-654-3210
    ```
