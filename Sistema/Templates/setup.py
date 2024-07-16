from setuptools import setup
from Cython.Build import cythonize

setup(
    ext_modules = cythonize("app.pyx")
)
# Executar no terminal: python3 setup.py build_ext --inplace
