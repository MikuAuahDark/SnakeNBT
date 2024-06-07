"""
SnakeNBT
=====

This module provides simple binary NBT decoding and encoding.

*****

Copyright (C) 2024 Miku AuahDark

This software is provided 'as-is', without any express or implied
warranty.  In no event will the authors be held liable for any damages
arising from the use of this software.

Permission is granted to anyone to use this software for any purpose,
including commercial applications, and to alter it and redistribute it
freely, subject to the following restrictions:

1. The origin of this software must not be misrepresented; you must not
   claim that you wrote the original software. If you use this software
   in a product, an acknowledgment in the product documentation would be
   appreciated but is not required.
2. Altered source versions must be plainly marked as such, and must not be
   misrepresented as being the original software.
3. This notice may not be removed or altered from any source distribution.
"""

import collections.abc
import io
import itertools
import struct

from typing import Any, Callable, Generic, TypeVar, Protocol, SupportsIndex, cast


_TagValue = TypeVar("_TagValue")


class Tag(Generic[_TagValue]):
    tag_id: int = 0

    def __init__(self, value: _TagValue, name: str | None = None):
        self._nbt_name = name
        self._nbt_value = value

    @property
    def tag_name(self):
        return self._nbt_name

    @tag_name.setter
    def tag_name(self, name: str | None):
        self._nbt_name = name
        return name

    @property
    def tag_value(self):
        return self._nbt_value

    @tag_value.setter
    def tag_value(self, value: _TagValue):
        self._nbt_value = value
        return value

    def tag_repr(self):
        return f"{self.__class__.__name__}({self.tag_value!r})"


class _TagRepr(Tag[_TagValue]):
    def __repr__(self):
        return self.tag_repr()


def _fix_integer_value(value: int, intsize: int):
    bitshift = 64 - intsize * 8
    sign_num = 0x8000000000000000 >> bitshift
    value = value & (0xFFFFFFFFFFFFFFFF >> bitshift)
    return (value ^ sign_num) - sign_num


class TagIntegers(_TagRepr[int], SupportsIndex):
    _integer_size: int = 0

    def __init__(self, value: int, name: str | None = None):
        super().__init__(_fix_integer_value(value, self._integer_size), name)

    def __int__(self) -> int:
        return self._nbt_value

    def __float__(self) -> float:
        return float(self._nbt_value)

    def __index__(self) -> int:
        return self._nbt_value.__index__()


class TagFloating(_TagRepr[float]):
    def __int__(self):
        return int(self._nbt_value)

    def __float__(self):
        return self._nbt_value


class TagEnd(Tag[None]):
    def __init__(self, value=None, name: str | None = None):
        super().__init__(value, name)


class TagByte(TagIntegers):
    tag_id: int = 1
    _integer_size: int = 1


class TagShort(TagIntegers):
    tag_id: int = 2
    _integer_size: int = 2


class TagInt(TagIntegers):
    tag_id: int = 3
    _integer_size: int = 4


class TagLong(TagIntegers):
    tag_id: int = 4
    _integer_size: int = 8


class TagFloat(TagFloating):
    tag_id: int = 5


class TagDouble(TagFloating):
    tag_id: int = 6


class _TagListPrimitive(Tag[list[_TagValue]], list[_TagValue]):
    def __init__(
        self,
        cls: type[_TagValue],
        value: collections.abc.Iterable[_TagValue] | None = None,
        name: str | None = None,
    ):
        if value is None:
            list.__init__(self)
        else:
            list.__init__(self, value)
        Tag.__init__(self, self, name)
        self._nbt_target_type = cls

    @property
    def tag_value(self):
        return self

    @tag_value.setter
    def tag_value(self, value: list[Tag[_TagValue]]):
        # immutable
        return self

    @property
    def tag_type(self):
        return self._nbt_target_type

    def append(self, value: _TagValue):
        if not isinstance(value, self._nbt_target_type):
            raise ValueError("invalid value type")

        return super().append(value)


class _TagListInts(_TagListPrimitive[int]):
    _integer_size: int = 0

    def __init__(self, value: collections.abc.Iterable[int] | None = None, name: str | None = None):
        super().__init__(
            int, None if value is None else (_fix_integer_value(int(v), self._integer_size) for v in value), name
        )


class TagList(_TagListPrimitive[Tag[_TagValue]]):
    tag_id: int = 9

    def __init__(
        self,
        value: collections.abc.Iterable[Tag[_TagValue]] | None = None,
        name: str | None = None,
        cls: type[Tag[_TagValue]] = Tag,
    ):
        super().__init__(cls, value, name)


class TagByteArray(_TagListInts):
    tag_id: int = 7
    _integer_size: int = 1

    def __bytes__(self):
        return bytes([v & 0xFF for v in self])


class TagString(Tag[str], str):
    tag_id: int = 8

    def __new__(cls, value: str, name: str | None = None):
        result = str.__new__(cls, value)
        Tag.__init__(result, result, name)
        return result

    def __init__(self, value: str, name: str | None = None):
        pass

    @property
    def tag_value(self):
        return self

    @tag_value.setter
    def tag_value(self, value: str):
        # immutable
        return self


class TagCompound(Tag[dict[str, Tag[Any]]], dict[str, Tag[Any]]):
    tag_id: int = 10

    def __init__(self, value: dict[str, Tag[Any]] | None = None, name: str | None = None):
        if value:
            dict.__init__(self, value)
        else:
            dict.__init__(self)
        Tag.__init__(self, self, name)

        for k, v in self.items():
            v.tag_name = k

    @property
    def tag_value(self):
        return self

    @tag_value.setter
    def tag_value(self, value: dict[str, Tag[Any]]):
        # immutable
        return self

    def __setitem__(self, key: str, item: Tag[Any]) -> None:
        if not isinstance(item, Tag):
            raise ValueError("invalid value type")

        super().__setitem__(key, item)
        item.tag_name = key


class TagIntArray(_TagListInts):
    tag_id: int = 11
    _integer_size: int = 4


class TagLongArray(_TagListInts):
    tag_id: int = 12
    _integer_size: int = 8


def _make_factory_2(cls: type[Tag[Any]]):
    def _wrap(value: Any, name: str | None = None, other: Any | None = None) -> Tag[Any]:
        return cls(value, name)

    return _wrap


_ALL_TAGS: tuple[type[Tag[Any]], ...] = (
    TagEnd,
    TagByte,
    TagShort,
    TagInt,
    TagLong,
    TagFloat,
    TagDouble,
    TagByteArray,
    TagString,
    TagList,
    TagCompound,
    TagIntArray,
    TagLongArray,
)
_ALL_TAGS_MINUS_TAG_LIST: tuple[type[Tag[Any]], ...] = (
    TagEnd,
    TagByte,
    TagShort,
    TagInt,
    TagLong,
    TagFloat,
    TagDouble,
    TagByteArray,
    TagString,
    TagCompound,
    TagIntArray,
    TagLongArray,
)

_TAG_ID_MAPPING = {cls.tag_id: cls for cls in _ALL_TAGS}

_DECODER_BY_TAG_TYPE: dict[int, Callable[[Any, str | None, Any], Any]] = dict(
    itertools.chain(
        ((cls.tag_id, _make_factory_2(cls)) for cls in _ALL_TAGS_MINUS_TAG_LIST),
        ((TagList.tag_id, TagList),),
    )
)


def _convert_dummy(value, name: str | None, other_data: Any | None):
    return value


def _convert_bytearray(value: bytes, name: str | None, other_data: Any | None):
    return list(value)


_DECODER_DUMMY_TYPE: dict[int, Callable[[Any, str | None, Any | None], Any]] = {
    TagEnd.tag_id: _convert_dummy,
    TagByte.tag_id: _convert_dummy,
    TagShort.tag_id: _convert_dummy,
    TagInt.tag_id: _convert_dummy,
    TagLong.tag_id: _convert_dummy,
    TagFloat.tag_id: _convert_dummy,
    TagDouble.tag_id: _convert_dummy,
    TagByteArray.tag_id: _convert_dummy,
    TagString.tag_id: _convert_dummy,
    TagList.tag_id: _convert_dummy,
    TagCompound.tag_id: _convert_dummy,
    TagIntArray.tag_id: _convert_dummy,
    TagLongArray.tag_id: _convert_dummy,
}


_DECODER_DUMMY_BYTEARRAY_AS_LIST_TYPE: dict[int, Callable[[Any, str | None, Any | None], Any]] = {
    TagEnd.tag_id: _convert_dummy,
    TagByte.tag_id: _convert_dummy,
    TagShort.tag_id: _convert_dummy,
    TagInt.tag_id: _convert_dummy,
    TagLong.tag_id: _convert_dummy,
    TagFloat.tag_id: _convert_dummy,
    TagDouble.tag_id: _convert_dummy,
    TagByteArray.tag_id: _convert_bytearray,
    TagString.tag_id: _convert_dummy,
    TagList.tag_id: _convert_dummy,
    TagCompound.tag_id: _convert_dummy,
    TagIntArray.tag_id: _convert_dummy,
    TagLongArray.tag_id: _convert_dummy,
}


class _SupportsByteRead(Protocol):
    def read(self, size: int | None = -1, /) -> bytes:
        ...


class _SupportsByteWrite(Protocol):
    def write(self, data: bytes, /) -> int:
        ...


def _from_java_utf8(data: bytes):
    return str(data.replace(b"\xC0\x80", b"\0"), "utf-8")


def _to_java_utf8(data: str):
    return data.encode("utf-8").replace(b"\0", b"\xC0\x80")


def _read_vlstring(fp: _SupportsByteRead):
    length: int = struct.unpack(">H", fp.read(2))[0]
    return _from_java_utf8(fp.read(length))


def _write_vlstring(fp: _SupportsByteWrite, string: str):
    bytestr = _to_java_utf8(string)
    length = len(bytestr)

    if length > 65535:
        raise ValueError(f"string {string[:35]} too long to encode")

    fp.write(length.to_bytes(2, "big"))
    fp.write(bytestr)


def _decode_python_by_tag_id(
    fp: _SupportsByteRead,
    tag_id: int,
    convert_map: dict[int, Callable[[Any, str | None, Any | None], Any]],
    name: str | None,
):
    other_data = None
    length: int
    python_data: int | bytes | str | list[Any] | dict[str, Any] | None
    match tag_id:
        case TagByte.tag_id:
            python_data = fp.read(1)[0]
        case TagShort.tag_id:
            python_data = struct.unpack(">h", fp.read(2))[0]
        case TagInt.tag_id:
            python_data = struct.unpack(">i", fp.read(4))[0]
        case TagLong.tag_id:
            python_data = struct.unpack(">q", fp.read(8))[0]
        case TagFloat.tag_id:
            python_data = struct.unpack(">f", fp.read(4))[0]
        case TagDouble.tag_id:
            python_data = struct.unpack(">d", fp.read(8))[0]
        case TagByteArray.tag_id:
            length = struct.unpack(">I", fp.read(4))[0]
            python_data = fp.read(length)
        case TagString.tag_id:
            python_data = _read_vlstring(fp)
        case TagList.tag_id:
            target_tag_id = fp.read(1)[0]
            length = struct.unpack(">I", fp.read(4))[0]
            python_data = []
            for _ in range(length):
                python_data.append(_decode_python_by_tag_id(fp, target_tag_id, convert_map, None))
            other_data = _TAG_ID_MAPPING[target_tag_id]
        case TagCompound.tag_id:
            python_data = {}

            while True:
                decoded_object, decoded_name = _decode(fp, convert_map, True)
                if decoded_object is None:
                    # TAG_End
                    break

                assert decoded_name is not None
                python_data[decoded_name] = decoded_object
        case TagIntArray.tag_id:
            length = struct.unpack(">I", fp.read(4))[0]
            python_data = []
            for _ in range(length):
                python_data.append(_decode_python_by_tag_id(fp, TagInt.tag_id, convert_map, None))
        case TagLongArray.tag_id:
            length = struct.unpack(">I", fp.read(4))[0]
            python_data = []
            for _ in range(length):
                python_data.append(_decode_python_by_tag_id(fp, TagLong.tag_id, convert_map, None))
        case _:
            python_data = None

    return convert_map[tag_id](python_data, name, other_data)


def _decode(
    fp: _SupportsByteRead, convert_map: dict[int, Callable[[Any, str | None, Any | None], Any]], decode_name: bool
):
    tag_id = fp.read(1)[0]
    if tag_id == 0:
        return None, None

    name = None
    if decode_name:
        name = _read_vlstring(fp)

    return _decode_python_by_tag_id(fp, tag_id, convert_map, name), name


def _guess_target_tag_id(data: collections.abc.Sequence[Any], deep: bool = True) -> tuple[int, int]:
    if isinstance(data, bytes):
        # TAG_Byte_Array
        return TagByteArray.tag_id, 0

    last = None
    target_list_type = 0
    bitsize = 0
    for value in data:
        value_type = type(value)
        if last is None:
            last = value_type
        elif last is not value_type:
            raise ValueError("cannot inference target tag for list")

        if value_type is int:
            bitsize = max(cast(int, value).bit_length(), bitsize)
        elif issubclass(value_type, collections.abc.Sequence) and deep:
            container_tag_id, _ = _guess_target_tag_id(cast(collections.abc.Sequence, value), False)
            if target_list_type == 0:
                target_list_type = container_tag_id
            elif target_list_type != container_tag_id:
                raise ValueError("cannot inference target tag for list")

    if last is None:
        return TagList.tag_id, TagEnd.tag_id
    elif last is int:
        # Get highest bit
        if bitsize > 64:
            raise ValueError(f"list of int too large to be encoded")
        elif bitsize > 32:
            return TagLongArray.tag_id, 0
        elif bitsize > 16:
            return TagIntArray.tag_id, 0
        elif bitsize > 8:
            return TagList.tag_id, TagShort.tag_id
        else:
            return TagByteArray.tag_id, 0
    elif last is float:
        return TagList.tag_id, TagDouble.tag_id
    elif issubclass(last, str):
        return TagList.tag_id, TagString.tag_id
    elif issubclass(last, collections.abc.Sequence):
        return TagList.tag_id, target_list_type
    elif issubclass(last, collections.abc.Mapping):
        return TagList.tag_id, TagCompound.tag_id

    raise ValueError("cannot inference target tag for list")


def _encode_value_tagged(fp: _SupportsByteWrite, value: Tag[Any], write_tag_id: int):
    if write_tag_id:
        fp.write(value.tag_id.to_bytes(1, "big"))
    if value.tag_name is not None:
        _write_vlstring(fp, value.tag_name)
    typed_value: TagByteArray | TagIntArray | TagLongArray | TagList[Tag[Any]]
    match value.tag_id:
        case TagEnd.tag_id:
            pass
        case TagByte.tag_id:
            fp.write(cast(TagByte, value).tag_value.to_bytes(1, "big", signed=True))
        case TagShort.tag_id:
            fp.write(cast(TagShort, value).tag_value.to_bytes(2, "big", signed=True))
        case TagInt.tag_id:
            fp.write(cast(TagInt, value).tag_value.to_bytes(4, "big", signed=True))
        case TagLong.tag_id:
            fp.write(cast(TagLong, value).tag_value.to_bytes(8, "big", signed=True))
        case TagFloat.tag_id:
            fp.write(struct.pack(">f", value.tag_value))
        case TagDouble.tag_id:
            fp.write(struct.pack(">d", value.tag_value))
        case TagByteArray.tag_id:
            typed_value = cast(TagByteArray, value)
            fp.write(struct.pack(">I", len(typed_value)))
            fp.write(bytes(typed_value))
        case TagString.tag_id:
            _write_vlstring(fp, cast(str, value))
        case TagList.tag_id:
            typed_value = cast(TagList[Tag[Any]], value)
            fp.write(typed_value.tag_type.tag_id.to_bytes(1, "big"))
            fp.write(struct.pack(">I", len(typed_value)))
            for v in typed_value:
                v.tag_name = None
                _encode_value(fp, v, None, False)
        case TagCompound.tag_id:
            for k, v in cast(TagCompound, value).items():
                v.tag_name = k
                _encode_value(fp, v, k, True)
            fp.write(TagEnd.tag_id.to_bytes(1, "big"))
        case TagIntArray.tag_id:
            typed_value = cast(TagIntArray, value)
            fp.write(struct.pack(">I", len(typed_value)))
            for i in typed_value:
                fp.write(i.to_bytes(4, "big", signed=True))
        case TagIntArray.tag_id:
            typed_value = cast(TagLongArray, value)
            fp.write(struct.pack(">I", len(typed_value)))
            for i in typed_value:
                fp.write(i.to_bytes(8, "big", signed=True))
        case _:
            raise TypeError(f"unknown tag id {value.tag_id:02x} of '{value.__class__.__name__}'")


def _get_intsize_by_tag_id(tag_id: int, for_arrays: bool):
    if for_arrays:
        match tag_id:
            case TagByteArray.tag_id:
                return 1
            case TagIntArray.tag_id:
                return 4
            case TagLongArray.tag_id:
                return 8
            case _:
                raise ValueError(f"Unknown tag id for arrays {tag_id}")
    else:
        match tag_id:
            case TagByte.tag_id:
                return 1
            case TagShort.tag_id:
                return 2
            case TagInt.tag_id:
                return 4
            case TagLong.tag_id:
                return 8
            case _:
                return 0


def _encode_value_primitive(
    fp: _SupportsByteWrite, value: Any, name: str | None, write_tag_id: bool, *, intsize: int = 0
):
    if isinstance(value, int):
        if intsize == 0:
            if value in range(-128, 128):
                intsize = 1
                value = value & 0xFF
                tag_id = TagByte.tag_id
            elif value in range(-32768, 32768):
                intsize = 2
                value = value & 0xFFFF
                tag_id = TagShort.tag_id
            elif value in range(-2147483648, 2147483648):
                intsize = 4
                value = value & 0xFFFFFFFF
                tag_id = TagInt.tag_id
            elif value in range(-9223372036854775808, 9223372036854775808):
                intsize = 8
                value = value & 0xFFFFFFFFFFFFFFFF
                tag_id = TagLong.tag_id
            else:
                raise ValueError(f"integer '{value}' too large to be encoded")
        else:
            if intsize > 8:
                raise ValueError(f"intsize '{intsize}' too large")
            elif intsize > 4:
                tag_id = TagLong.tag_id
            elif intsize > 2:
                tag_id = TagInt.tag_id
            elif intsize > 1:
                tag_id = TagShort.tag_id
            else:
                tag_id = TagByte.tag_id
        if write_tag_id:
            fp.write(tag_id.to_bytes(1, "big"))
        if name is not None:
            _write_vlstring(fp, name)
        fp.write(value.to_bytes(intsize, "big"))
    elif isinstance(value, float):
        # Assume double-precision for now
        if write_tag_id:
            fp.write(TagDouble.tag_id.to_bytes(1, "big"))
        if name is not None:
            _write_vlstring(fp, name)
        fp.write(struct.pack(">d", value))
    elif isinstance(value, str):
        if write_tag_id:
            fp.write(TagString.tag_id.to_bytes(1, "big"))
        if name is not None:
            _write_vlstring(fp, name)
        _write_vlstring(fp, value)
    elif isinstance(value, collections.abc.Sequence):
        # List, but list of what?
        arrlen = len(value)
        if arrlen > 0x7FFFFFFF:
            raise ValueError("list too long")

        container_tag_id, target_type_tag_id = _guess_target_tag_id(value, True)
        if write_tag_id:
            fp.write(container_tag_id.to_bytes(1, "big"))
        if name is not None:
            _write_vlstring(fp, name)
        if container_tag_id == TagList.tag_id:
            # Ordinary TAG_List
            fp.write(target_type_tag_id.to_bytes(1, "big"))
            fp.write(arrlen.to_bytes(4, "big"))

            for v in value:
                _encode_value(fp, v, None, False, intsize=_get_intsize_by_tag_id(target_type_tag_id, False))
        else:
            # Integer arrays
            fp.write(arrlen.to_bytes(4, "big"))
            for v in value:
                _encode_value(fp, v, None, False, intsize=_get_intsize_by_tag_id(container_tag_id, True))

    elif isinstance(value, collections.abc.Mapping):
        # Dictionary, which means compound.
        if write_tag_id:
            fp.write(TagCompound.tag_id.to_bytes(1, "big"))
        if name is not None:
            _write_vlstring(fp, name)

        for k, v in value.items():
            _encode_value(fp, v, k, True)

        fp.write(TagEnd.tag_id.to_bytes(1, "big"))
    else:
        raise TypeError(f"unknown type to encode '{value.__class__.__name__}'")


def _encode_value(fp: _SupportsByteWrite, value: Any, name: str | None, write_tag_id: bool, *, intsize: int = 0):
    if isinstance(value, Tag):
        _encode_value_tagged(fp, value, write_tag_id)
    else:
        _encode_value_primitive(fp, value, name, write_tag_id, intsize=intsize)


def load(
    fp: _SupportsByteRead,
    *,
    preserve_tag_type: bool = False,
    root_has_name: bool = True,
    byte_array_as_bytes: bool = True,
) -> Any:
    convert_map = (
        _DECODER_BY_TAG_TYPE
        if preserve_tag_type
        else (_DECODER_DUMMY_TYPE if byte_array_as_bytes else _DECODER_DUMMY_BYTEARRAY_AS_LIST_TYPE)
    )
    return _decode(fp, convert_map, root_has_name)[0]


def loads(
    s: bytes, *, preserve_tag_type: bool = False, root_has_name: bool = True, byte_array_as_bytes: bool = True
) -> Any:
    with io.BytesIO(s) as fp:
        return load(
            fp,
            preserve_tag_type=preserve_tag_type,
            root_has_name=root_has_name,
            byte_array_as_bytes=byte_array_as_bytes,
        )


def dump(obj: Any, fp: _SupportsByteWrite, *, root_name: str | None = "") -> None:
    if isinstance(obj, Tag):
        root_name = obj.tag_name
    _encode_value(fp, obj, root_name, True)


def dumps(obj: Any, *, root_name: str | None = "") -> bytes:
    with io.BytesIO() as f:
        dump(obj, f, root_name=root_name)
        return f.getvalue()
