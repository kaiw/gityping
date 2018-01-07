
#: List of attributes on introspected objects to be skipped
ATTR_IGNORE_LIST = [
    # In (almost?) all cases, this annotation should be on the init
    'new',
    # Private!
    'priv',
    # TODO: It's possible we can add annotations here, but for now it's
    # too hard.
    'widget',
]

MODULES = (
    ('GObject', '2.0'),
    ('GLib', '2.0'),
    ('Gdk', '3.0'),
    ('Gtk', '3.0'),
    ('Gio', '2.0'),
    ('GtkSource', '3.0'),
    ('Pango', '1.0'),
    ('GdkPixbuf', '2.0'),
    ('cairo', '1.0'),
)
