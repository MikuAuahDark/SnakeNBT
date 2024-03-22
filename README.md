🐍 SnakeNBT 🐍
=====

Yet another NBT encoder/decoder written in Python.

It's single file for easiest integration in your existing project too.

Why?
-----

* None of Python NBT libraries has [`json`](https://docs.python.org/3/library/json.html) and [`pickle`](https://docs.python.org/3/library/pickle.html)-like `load/s` and `dump/s` API.
* None of them uses strong type annotations.

Example
-----

### Loading uncompressed NBT
```py
import snakenbt

with open("uncompressed.nbt", "rb") as f:
	nbt_data = snakenbt.load(f)
```

### Loading gzipped NBT
```py
import gzip
import snakenbt

with gzip.open("compressed.nbt", "rb") as f:
	nbt_data = snakenbt.load(f)
```

### Preserving the tag types

With 2 examples above, the tag information is lost. To preserve them, add `preserve_tag_type=True`.

```py
import gzip
import snakenbt

with gzip.open("compressed.nbt", "rb") as f:
	nbt_data = snakenbt.load(f, preserve_tag_type=True)
```

Now `nbt_data` will return the respective NBT tag classes.

### Loading NBT data from memory

```py
import snakenbt

nbt_data = snakenbt.loads(encoded_nbt_data_as_bytes)
```

Again, it follows `json` and `pickle` `load/s` and `dump/s` API.

### Writing to NBT

```py
import snakenbt

encoded_nbt = snakenbt.dumps(nbt_data)
```

If `nbt_data` is not `Tag*` `snakenbt` types, `snakenbt` will try to guess the types. This may not what you want.

Types
-----

Here are the conversion table between NBT and Python types.

| NBT Tag        | `snakenbt` type | Python Type              |
|----------------|-----------------|--------------------------|
| TAG_End        | `TagEnd`        | `None`                   |
| TAG_Byte       | `TagByte`       | `int`                    |
| TAG_Short      | `TagShort`      | `int`                    |
| TAG_Int        | `TagInt`        | `int`                    |
| TAG_Long       | `TagLong`       | `int`                    |
| TAG_Float      | `TagFloat`      | `float`                  |
| TAG_Double     | `TagDouble`     | `float`                  |
| TAG_Byte_Array | `TagByteArray`* | `list[int]` or `bytes`** |
| TAG_String     | `TagString`*    | `str`                    |
| TAG_List       | `TagList`*      | `list[Any]`              |
| TAG_Compound   | `TagCompound`*  | `dict[str, Any]`         |
| TAG_Int_Array  | `TagIntArray`*  | `list[int]`              |
| TAG_Long_Array | `TagLongArray`* | `list[int]`              |

\* `snakenbt` types marked with asterisk were also its underlying Python type (e.g. `TagCompound` is also a Python
`dict`, `TagString` is also a Python `str`, etc.), so standard Python operators on the respective Python types were
supported (e.g. `TagList.append`, `TagString.upper`, etc.). This means `tag_value` setter is no-op as
`tag.tag_value is tag` evaluates to `True`.  
\*\* Use `byte_array_as_bytes=True` to get `bytes` object instead of `list[int]`.

When setting `preserve_tag_type=True`, the NBT will be converted to the `snakenbt` types that derive from
`snakenbt.Tag`. Otherwise, it's converted directly to the respective Python types. `snakenbt.Tag` additionally has
these properties:
* `tag_name` - Tag name
* `tag_value` - Underlying tag value.
* `tag_type` - `snakenbt` tag class which `TagList` members of (for `TagList` only).

For integer and floating types, use `int(x)` to get the (truncated) Python integer value of the `snakenbt` types.
Additionally for floating types, use `float(x)` to get the Python `float` value of the `snakenbt` types.

Things to do
-----

* Allow serialization of `dataclass`-like types (this includes PyDantic types).
* Allow one-dimensional NumPy arrays and PyTorch tensors for `TAG_Byte_Array`, `TAG_Int_Array` and `TAG_Long_Array`.
