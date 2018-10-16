
import pathlib

from setuptools import find_packages, setup


readme = pathlib.Path(__file__).resolve().with_name('README.md')

setup(
    name='gityping',
    version='0.1',
    description='Python typing annotations for GObject introspection bindings',
    long_description=readme.read_text(),
    url='https://github.com/kaiw/gityping',
    author='Kai Willadsen',
    author_email='kai.willadsen@gmail.com',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Quality Assurance',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    packages=find_packages(exclude=['tests']),
    # We make no sense without gobject-introspection installed, but
    # can't validate that here.
    install_requires=[
      'click',
      'pygobject',
    ],
    entry_points={
        'console_scripts': [
            'gityping=gityping.main:main',
        ],
    },
)
