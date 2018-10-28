import enum
import inspect
import io
import logging
import types
import typing

from gi._gi import (
    CallableInfo,
    Direction,
    EnumInfo,
    FieldInfo,
    FunctionInfo,
    InterfaceInfo,
    ObjectInfo,
    RegisteredTypeInfo,
    StructInfo,
    TypeInfo,
    TypeTag,
    UnionInfo,
    VFuncInfo,
)
from gi.module import IntrospectionModule
from gi.repository import GObject

from .const import (
    ATTR_IGNORE_LIST,
    PYGI_BOOL_OVERRIDE_FN,
    PYGI_STATIC_BINDINGS,
)


log = logging.getLogger(__name__)


class GTypeTag(enum.IntEnum):
    ARRAY = TypeTag.ARRAY
    BOOLEAN = TypeTag.BOOLEAN
    DOUBLE = TypeTag.DOUBLE
    ERROR = TypeTag.ERROR
    FILENAME = TypeTag.FILENAME
    FLOAT = TypeTag.FLOAT
    GHASH = TypeTag.GHASH
    GLIST = TypeTag.GLIST
    GSLIST = TypeTag.GSLIST
    GTYPE = TypeTag.GTYPE
    INT16 = TypeTag.INT16
    INT32 = TypeTag.INT32
    INT64 = TypeTag.INT64
    INT8 = TypeTag.INT8
    INTERFACE = TypeTag.INTERFACE
    UINT16 = TypeTag.UINT16
    UINT32 = TypeTag.UINT32
    UINT64 = TypeTag.UINT64
    UINT8 = TypeTag.UINT8
    UNICHAR = TypeTag.UNICHAR
    UTF8 = TypeTag.UTF8
    VOID = TypeTag.VOID

    @classmethod
    def from_typeinfo(cls, typeinfo):
        type_tag = typeinfo.get_tag()
        return cls(type_tag)

    def as_pytype(self):
        mapping = {
            GTypeTag.ARRAY: list,
            GTypeTag.BOOLEAN: bool,
            GTypeTag.DOUBLE: float,
            GTypeTag.ERROR: 'gi.repository.GLib.Error',
            GTypeTag.FILENAME: str,
            GTypeTag.FLOAT: float,
            GTypeTag.GHASH: dict,
            GTypeTag.GLIST: list,
            GTypeTag.GSLIST: list,
            GTypeTag.GTYPE: 'gi.repository.GObject.GType',
            GTypeTag.INT16: int,
            GTypeTag.INT32: int,
            GTypeTag.INT64: int,
            GTypeTag.INT8: int,
            # We shouldn't typing.Any here, but currently this occurs
            # only once in a context in which GTypeTag is used, and
            # it's not worth the additional introspection complication.
            GTypeTag.INTERFACE: 'typing.Any',
            GTypeTag.UINT16: int,
            GTypeTag.UINT32: int,
            GTypeTag.UINT64: int,
            GTypeTag.UINT8: int,
            GTypeTag.UNICHAR: str,
            GTypeTag.UTF8: str,
            GTypeTag.VOID: None,
        }
        return mapping[self]


# TODO: Add annotations for gobject properties
# TODO: Add annotations for gobject signals


current_stub_module = None
current_gi_imports = set()


def get_current_module_name():
    # This basically exists so that you can use functions from a REPL
    return getattr(current_stub_module, '__name__', 'I_AM_BROKEN')


def get_effective_module(module):
    if module.startswith('gi.overrides'):
        newmodule = 'gi.repository' + module[len('gi.overrides'):]
        log.debug(
            'Rewriting module name from {} to {}'.format(module, newmodule))
        return newmodule
    return module


def format_cls_name(cls):
    if isinstance(cls, RegisteredTypeInfo):
        info = cls
    else:
        info = getattr(cls, '__info__', None)
    if info:
        if info.get_namespace() == 'GObject' and info.get_name() == 'Object':
            return 'GObject'
    return cls.__name__


def format_module(cls):
    module_name = get_effective_module(cls.__module__)
    cls_name = format_cls_name(cls)

    if module_name == get_current_module_name():
        return cls_name
    current_gi_imports.add(module_name)
    return '{}.{}'.format(module_name, cls_name)


def format_gi_class(cls):
    name = format_cls_name(cls)

    parent_cls = None
    if hasattr(cls, '__gtype__'):
        parent_cls = cls.__gtype__.parent.pytype

    if parent_cls:
        return "class {}({}):".format(
            name, format_module(parent_cls))

    return "class {}:".format(name)


def get_typeinfo(typeinfo: TypeInfo):
    """Obtain a python-style type annotation for the given TypeInfo

    This is currently only called when handling function arguments and
    return values. As such, it doesn't handle all possible `TypeInfo`s.
    """

    type_tag = GTypeTag.from_typeinfo(typeinfo)

    if type_tag == GTypeTag.INTERFACE:
        iface = typeinfo.get_interface()

        # At this point we have an interface. This may be a GObject
        # subclass with a fundamental GType like a GEnum, or it could
        # be a full GObject class, or it could be a callback or
        # similar.

        if isinstance(iface, CallableInfo):
            signature, preamble = make_signature(iface)

            def format_annotation(annotation):
                if annotation is None or isinstance(
                        annotation, inspect.Parameter.empty):
                    # FIXME: Can we do any better than Any?
                    return 'typing.Any'
                if isinstance(annotation, type):
                    return annotation.__name__
                # Object and GObject are the same, but normalising here
                # makes everything nicer
                if annotation == 'gi.repository.GObject.Object':
                    annotation = 'gi.repository.GObject.GObject'
                return annotation

            args = [
                format_annotation(v.annotation)
                for v in signature.parameters.values()
            ]
            return_type = format_annotation(signature.return_annotation)

            return "typing.Callable[[{arg_types}], {return_type}]".format(
                arg_types=', '.join(a for a in args),
                return_type=return_type,
            )
        elif isinstance(iface, RegisteredTypeInfo):
            # TODO: The following block attempts to handle missing type
            # information, but in all cases I've checked, the default
            # format_module() treatment works just fine. Keeping this
            # code block in place but disabled until I can confirm.
            if False and iface.get_g_type() == GObject.TYPE_NONE:
                # This may be a gpointer, although in at least some
                # cases the gpointer in question has additional type
                # annotations; it's unclear what's going on here.
                return typing.Any
            return format_module(iface)

    # TODO: This handles basic types, but handling for, lists, hashes,
    # etc. is at best partial.
    pytype = type_tag.as_pytype()
    if pytype == list:
        # TODO: pygobject removes length parameters associated with
        # arrays based on extra annotations. We don't yet handle this.
        if type_tag == TypeTag.ARRAY:
            # FIXME: We should be able to get the array offset by using
            # typeinfo.get_array_length(), though the docs aren't clear
            # on how this is used.
            log.info("Missing array length argument handling!")

        # This is undocumented, but... appears correct?
        list_type = get_typeinfo(typeinfo.get_param_type(0))
        return "typing.List[{list_type}]".format(
            list_type=format_pytype(list_type))

    if type_tag == GTypeTag.VOID and typeinfo.is_pointer():
        # This is probably an opaque gpointer; we don't know anything
        # about this, so mark it accordingly.
        pytype = "typing.Any"

    if pytype is None and type_tag != GTypeTag.VOID:
        print("Incomplete tag mapping for {}".format(type_tag))

    return pytype


def get_argument_info(arg_info):
    # TODO: We can't do this. The argument list is stateful because of
    # (at least) array length arguments, so we need to maintain some
    # state of the type parsing in between everything and return a
    # reconstucted argument list at the end.

    type_annotation = get_typeinfo(arg_info.get_type())

    if type_annotation is None:
        type_tag = GTypeTag.from_typeinfo(arg_info.get_type())
        if type_tag != GTypeTag.VOID:
            print(
                "missing type annotation for {} {}; "
                "built-in annotation was {}".format(
                    type_tag,
                    arg_info.get_name(),
                    getattr(arg_info.get_container(), '__doc__', '')))

    # FIXME: At this point, type_annotation will be the class. For gi
    # types, this means that it might be from the override module or
    # similar, and won't have the module stripping that we apply
    # elsewhere.
    return arg_info.get_name(), type_annotation, arg_info.get_direction()


def details_from_funcinfo(function, *, strip_bool_result=False):

    # TODO: Also handle getters, setters, etc.?

    # `CallableInfo` doesn't have `is_method` or `is_constructor`,
    # thus this exception handling.
    try:
        needs_self = isinstance(function, VFuncInfo) or function.is_method()
    except AttributeError:
        needs_self = False
    try:
        is_static = not needs_self and (
            function.is_constructor() or function.get_container() is not None)
    except AttributeError:
        is_static = False

    # There's no context to determine classmethod vs. staticmethod
    # here, but sampling a few headers they're all static.
    preamble = "@staticmethod" if is_static else ""

    parameters = []
    if needs_self:
        self_param = inspect.Parameter(
            'self',
            kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
        parameters.append(self_param)

    return_types = [get_typeinfo(function.get_return_type())]

    for argument in function.get_arguments():
        name, annotation, direction = get_argument_info(argument)
        # FIXME: INOUT should possibly be treated differently here.
        if direction in (Direction.IN, Direction.INOUT):
            parameter = inspect.Parameter(
                name,
                annotation=annotation,
                # TODO: I think this is actually true for gi... maybe?
                kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
            parameters.append(parameter)
        else:
            return_types.append(annotation)

    # If the function was wrapped with the strip_bool_result decorator
    # then we just remove the first return type to emulate that.
    if strip_bool_result:
        if return_types[0] != bool:
            raise RuntimeError('Tried to strip a non-boolean return type')
        return_types = return_types[1:]
        if not return_types:
            raise RuntimeError('No returns left after boolean stripping')

    if len(return_types) == 1:
        return_type = return_types[0]
    else:
        # Remove None returns in a list; these are functions with OUT
        # params that have gained a real Python return type.
        return_types = [r for r in return_types if r is not None]
        return_type_strs = [format_pytype(r) for r in return_types]
        return_type = 'typing.Tuple[{}]'.format(', '.join(return_type_strs))

    return preamble, parameters, return_type


def make_signature(function, *, strip_bool_result=False):
    if isinstance(function, CallableInfo):
        preamble, parameters, return_type = details_from_funcinfo(
            function, strip_bool_result=strip_bool_result)
        signature = inspect.Signature(
            parameters=parameters,
            return_annotation=return_type,
        )
    elif isinstance(function, types.FunctionType):
        # FIXME: We could have a static method here, but at this point
        # we don't have the necessary information to tell. We'd need to
        # have the defining class here and then do e.g.,
        #     isinstance(cls.__dict__['from_floats'], staticmethod)
        preamble = ""
        signature = inspect.signature(function)

        def sanitise_param_default(param):
            if str(param.default).startswith('<'):
                return param.replace(default=inspect.Parameter.empty)
            return param
        sanitised_params = [
            sanitise_param_default(v) for v in signature.parameters.values()
        ]
        signature = signature.replace(parameters=sanitised_params)
    else:
        raise NotImplementedError
    return signature, preamble


def format_pytype(pytype):
    if isinstance(pytype, type):
        return pytype.__name__
    return pytype


def format_variable(name, value):
    if inspect.isclass(value):
        type_str = format_module(value.__class__)
    else:
        type_str = type(value).__name__
    return "{} = ...  # type: {}".format(name, type_str)


def format_property(name, value, annotations):
    """Handle pure-Python property additions in overrides"""

    annotation = annotations.get(name)
    type_str = annotation.__name__ if annotation else typing.Any
    return "{} = ...  # type: {}".format(name, type_str)


def format_fieldinfo(attr_name, fieldinfo: FieldInfo):
    pytype = get_typeinfo(fieldinfo.get_type())
    return "{} = ...  # type: {}".format(attr_name, format_pytype(pytype))


def format_functioninfo(attr_name, func_info, *, strip_bool_result=False):
    assert isinstance(func_info, (VFuncInfo, FunctionInfo, types.FunctionType))

    try:
        signature, preamble = make_signature(
            func_info, strip_bool_result=strip_bool_result)
    except Exception as e:
        raise ValueError(
            "couldn't make signature for {}: {}".format(attr_name, e))

    if preamble:
        preamble += "\n"

    return (
        "{}"
        "def {}{}: ...\n"
    ).format(preamble, attr_name, signature)


def attr_generator(cls, attrs):
    for attr_name in attrs:

        # Simple ignore for things we know don't want annotations
        if attr_name.startswith('__') or attr_name in ATTR_IGNORE_LIST:
            continue

        if not attr_name.isidentifier():
            print("Invalid identifier {} found; skipping".format(
                attr_name))
            continue

        try:
            yield attr_name, getattr(cls, attr_name)
        except AttributeError as e:
            # Silently skip errors from static binding classes. See the
            # PYGI_STATIC_BINDINGS definition for details.
            if cls.__name__ not in PYGI_STATIC_BINDINGS:
                log.error(
                    'Error generating attributes (possibly a new '
                    'static binding): {}'.format(e))


def generic_attr_stubber(cls, attr_name, attr, stub_out):
    # Ordering is important here. We need to handle e.g., GFlags
    # before we fall back to int/str/float.

    annotations = typing.get_type_hints(cls)

    # TODO: Consider whether we can remove our struct-specific stubber
    # and just use this instead.
    try:
        cls_fields = {f.get_name(): f for f in cls.__info__.get_fields()}
    except AttributeError:
        cls_fields = {}

    if isinstance(attr, types.FunctionType) and hasattr(attr, '__wrapped__'):
        # FIXME: move this special handling elsewhere
        if attr.__qualname__.startswith(PYGI_BOOL_OVERRIDE_FN):
            fn_str = format_functioninfo(
                attr_name, attr.__wrapped__, strip_bool_result=True)
        else:
            log.warn('Unhandled function wrapper {} for {}.{}'.format(
                attr.__qualname__, format_cls_name(cls), attr_name))
            fn_str = format_functioninfo(attr_name, attr.__wrapped__)
        stub_out(fn_str)
    elif isinstance(attr, (VFuncInfo, FunctionInfo)):
        stub_out(format_functioninfo(attr_name, attr))
    elif (isinstance(attr, types.FunctionType) and
            cls.__module__.startswith('gi.overrides')):
        # This separately handles pure-Python override functions,
        # although at the moment we don't do anything here because none
        # of them have their own annotations.
        stub_out(format_functioninfo(attr_name, attr))
    elif attr_name in cls_fields:
        stub_out(format_fieldinfo(attr_name, cls_fields[attr_name]))
    elif (isinstance(attr, property) and
            cls.__module__.startswith('gi.overrides')):
        stub_out(format_property(attr_name, attr, annotations))
    elif isinstance(attr, (GObject.GType, GObject.GFlags, GObject.GEnum)):
        # TODO: unsure here. just annotate as the parent type? This is the
        # same as below. Do I want this clause for clarity, or what?
        stub_out(format_variable(attr_name, attr))
    elif isinstance(attr, (int, str, float)):
        stub_out(format_variable(attr_name, attr))
    else:
        print("unsupported type {} for {}.{}".format(
            type(attr), format_cls_name(cls), attr_name))


def generate_gobject_stubs(cls, attrs, stub_out):
    for attr_name, attr in attr_generator(cls, attrs):
        generic_attr_stubber(cls, attr_name, attr, stub_out)


def generate_genum_stub(cls, attrs, stub_out):

    # For enums (and flags) we would ideally use the available
    # get_values() introspection. However, the value names are
    # remapped (usually just upper-cased) so instead we go with this.

    if cls.__info__.is_flags():
        expected_values = [int(f) for f in cls.__flags_values__.values()]
    else:
        expected_values = cls.__enum_values__.values()

    for attr_name, attr in attr_generator(cls, attrs):
        if attr_name == 'LEVEL_MASK':
            # Handle OverflowError for GLib.LogLevelFlags.LEVEL_MASK;
            # see GNOME/pygobject#269 for details.
            pass
        else:
            if not attr_name.isupper() or attr not in expected_values:
                if isinstance(attr, FunctionInfo):
                    stub_out(format_functioninfo(attr_name, attr))
                    continue
                log.warn(
                    "Skipping unexpected attribute {} in enum {}".format(
                        attr_name, cls))
                continue

        stub_out(format_variable(attr_name, attr))


def generate_struct_stub(cls, attrs, stub_out):

    # For wrapped structs, the attrs are property objects, so we don't
    # have the same introspection data present. Instead, we use some
    # struct-specific fields + methods introspection.
    field_map = {f.get_name(): f for f in cls.__info__.get_fields()}
    method_map = {m.get_name(): m for m in cls.__info__.get_methods()}

    for attr_name, attr in attr_generator(cls, attrs):
        if attr_name in field_map:
            stub_out(format_fieldinfo(attr_name, field_map[attr_name]))
        elif attr_name in method_map:
            stub_out(format_functioninfo(attr_name, method_map[attr_name]))
        else:
            raise NotImplementedError(
                "Struct {} attribute {} is not in field or method map".format(
                      cls, attr_name))


def generate_class_stubs(module, cls):
    # FIXME: Don't take the stub_str; just make a new one per class and
    # concatenate them

    log.debug("Generating stubs for {}".format(cls))

    stub_lines = ['']

    # TODO: Investigate additional bases; see handling for ObjectInfo
    # multiple interfaces in  gi.module.IntrospectionModule.__getattr__
    stub_lines.append(format_gi_class(cls))

    # Sorting for consistency, but also so we're operating on a list copy
    attrs = sorted(cls.__dict__.keys())

    def stub_out(stub):
        for line in stub.splitlines():
            if line.strip():
                line = "    {}".format(line).rstrip()
            stub_lines.append(line)

    # FIXME: GBoxed doesn't have __info__
    try:
        info = cls.__info__
    except AttributeError:
        log.error("Introspected class does not have info: {}".format(cls))
        # FIXME: This is broken for many fundamental types as well
        generate_gobject_stubs(cls, attrs, stub_out)
        stub_out("...")
        return stub_lines

    # At this point, everything we should be dealing with is a
    # RegisteredTypeInfo subclass.

    if isinstance(info, (ObjectInfo, InterfaceInfo)):
        generate_gobject_stubs(cls, attrs, stub_out)
    elif isinstance(info, (StructInfo, UnionInfo)):
        # TODO: Should UnionInfo have different handling?
        generate_struct_stub(cls, attrs, stub_out)
    elif isinstance(info, EnumInfo):
        generate_genum_stub(cls, attrs, stub_out)
    else:
        raise NotImplementedError

    stub_out("...")
    return stub_lines


def generate_module_stub(module):
    stub_str = io.StringIO()

    log.debug("Generating module stubs for {}".format(module))

    # FIXME: This is wild. Basically, we need a state object at this point
    global current_stub_module
    global current_gi_imports
    current_stub_module = module
    # We use typing types in a bunch of places; easier to just add this now
    current_gi_imports = {'typing'}

    attrs = module.__dict__

    if not (
            isinstance(module, IntrospectionModule) or
            hasattr(module, '_introspection_module')):
        raise RuntimeError(
            f'tried to generate a stub for non-introspection module {module}')

    # This trick handles module-level lazy loading for e.g., annotating
    # the top-level Gdk namespace.
    if hasattr(module, '_introspection_module'):
        # This module has overrides.
        for attr in dir(module):
            getattr(module, attr)
        attrs.update(module._introspection_module.__dict__)
    elif isinstance(module, IntrospectionModule):
        # This module does not have overrides.
        for attr in dir(module):
            getattr(module, attr)

    attrs = sorted(attrs)

    attr_stubs = []

    for attr_name, attr in attr_generator(module, attrs):
        # FIXME: there's way too much overlap here with
        # generate_gobject_stubs; this could be a lot simpler.

        # FIXME: Ideally, generic_attr_stubber would handle classes as well,
        # but this requires it to understand nesting for correct indentation.
        if inspect.isclass(attr):
            if attr_name.endswith(('Class', 'Private')):
                log.debug(
                    'Skipping GObject-style internal class {}'.format(
                        attr_name))
                continue

            if attr.__module__ in ('gi._glib',):
                log.debug(
                    'Skipping statically bound class {}'.format(
                        attr_name))
                continue

            attr_stubs.append('')
            attr_stubs.extend(generate_class_stubs(module, attr))

        else:
            generic_attr_stubber(module, attr_name, attr, attr_stubs.append)

    stub_str = "\n".join(
        "import {}".format(imp) for imp in sorted(current_gi_imports)
    ) + "\n" + "\n".join(attr_stubs)
    return stub_str
