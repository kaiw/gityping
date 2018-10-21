
from gityping.gityping import generate_class_stubs


def test_gdk_color():
    from gi.repository import Gdk
    stub_lines = generate_class_stubs(Gdk, Gdk.Color)
    print("\n".join(stub_lines))

    foo = """
class Color:
    MAX_VALUE = ...  # type: int
    blue = ...  # type: int
    blue_float = ...  # type: typing.Any
    def copy(self) -> 'gi.repository.Gdk.Color': ...
    def equal(self, colorb:'gi.repository.Gdk.Color') -> bool: ...
    def free(self) -> None: ...
    @staticmethod
    def from_floats(self, red, green, blue): ...
    green = ...  # type: int
    green_float = ...  # type: typing.Any
    def hash(self) -> int: ...
    @staticmethod
    def parse(spec:str, color:'gi.repository.Gdk.Color') -> bool: ...
    pixel = ...  # type: int
    red = ...  # type: int
    red_float = ...  # type: typing.Any
    def to_floats(self): ...
    def to_string(self) -> str: ...
    ...
"""
    assert stub_lines == foo.splitlines()
