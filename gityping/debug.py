from gi._gi import InfoType


INFOTYPE_MAP = {
    InfoType.INVALID: "invalid type",
    InfoType.FUNCTION: "function",  # see GIFunctionInfo
    InfoType.CALLBACK: "callback",  # see GIFunctionInfo
    InfoType.STRUCT: "struct",  # see GIStructInfo
    InfoType.BOXED: "boxed",  # see GIStructInfo or GIUnionInfo
    InfoType.ENUM: "enum",  # see GIEnumInfo
    InfoType.FLAGS: "flags",  # see GIEnumInfo
    InfoType.OBJECT: "object",  # see GIObjectInfo
    InfoType.INTERFACE: "interface",  # see GIInterfaceInfo
    InfoType.CONSTANT: "contant",  # see GIConstantInfo
    InfoType.INVALID_0: "invalidated",  # used to be valid, but no alas
    InfoType.UNION: "union",  # see GIUnionInfo
    InfoType.VALUE: "enum value",  # see GIValueInfo
    InfoType.SIGNAL: "signal",  # see GISignalInfo
    InfoType.VFUNC: "virtual function",  # see GIVFuncInfo
    InfoType.PROPERTY: "GObject property",  # see GIPropertyInfo
    InfoType.FIELD: "struct or union field",  # see GIFieldInfo
    InfoType.ARG: "argument of a function or callback",  # see GIArgInfo
    InfoType.TYPE: "type information",  # see GITypeInfo
    # a type which is not present in the typelib, or any of its dependencies
    InfoType.UNRESOLVED: "unresolved type",
}


def debug_lineage(typeinfo):
    # TODO: This can be useful for debugging troublesome typeinfos, but
    # has the downside of being unassailably disgusting.
    debug = ""
    while typeinfo:
        name = '???'
        if hasattr(typeinfo, 'get_name'):
            name = typeinfo.get_name()
        namespace = '???'
        if hasattr(typeinfo, 'get_namespace'):
            namespace = typeinfo.get_namespace()
        typeinfo = typeinfo.get_container()
        debug = name + '.' + debug
        if typeinfo is None:
            debug = namespace + '.' + debug
    print("DEBUG:", debug)


def debug_interface(iface):
    iface_type = iface.get_type()
    print(
        "INTERFACE",
        iface,
        "{} ({})".format(INFOTYPE_MAP[iface_type], iface_type),
        getattr(iface, 'get_g_type', lambda: None)()
    )
