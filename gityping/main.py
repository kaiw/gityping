import collections
import importlib
import logging
import logging.config
import sys
from pathlib import Path

import click

from .const import MODULES
from .gityping import generate_module_stub


def ensure_module(stubs_base_path: Path, module) -> Path:
    *parent, name = module.__name__.split('.')
    path = stubs_base_path.joinpath(*parent)
    path.mkdir(parents=True, exist_ok=True)

    current = path
    while current != stubs_base_path:
        package_marker = current / '__init__.py'
        if not package_marker.exists():
            package_marker.touch()
        current = current.parent
    return path / '{}.pyi'.format(name)


def write_to_stubs(module, stub_str: str, stubs_base_path: Path):
    stub_file = ensure_module(stubs_base_path, module)
    with stub_file.open('w') as f:
        f.write(stub_str)


def get_modules():
    """Get a dictionary of actual imported modules to annotate

    This can be used interactively like:
        from gityping import *; globals().update(gimme())
    """
    import gi

    modules = collections.OrderedDict()

    for name, version in MODULES:
        gi.require_version(name, version)
        module = importlib.import_module('gi.repository.{}'.format(name))
        modules[name] = module

    return modules


def setup_logging(debug):
    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': '[%(levelname)s] %(message)s',
            },
        },
        'handlers': {
            'default': {
                'formatter': 'standard',
                'class': 'logging.StreamHandler',
                'stream': sys.stdout if debug else sys.stderr,
            },
        },
        'loggers': {
            '': {
                'handlers': ['default'],
                'level': logging.DEBUG if debug else logging.INFO,
                'propagate': True,
            },
        }
    }
    logging.config.dictConfig(config)


@click.command()
@click.argument('modules', default=None, nargs=-1)
@click.option('--debug', is_flag=True, default=False)
def main(modules, debug):
    setup_logging(debug)

    stub_base = Path('stubs')
    module_dict = get_modules()
    if modules:
        module_dict = {k: v for k, v in module_dict.items() if k in modules}
    for module in module_dict.values():
        stub = generate_module_stub(module)
        write_to_stubs(module, stub, stub_base)
