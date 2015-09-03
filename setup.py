from distutils.core import setup

setup(
    name='vivo-pump',
    version='0.61',
    url='https://github.com/mconlon17/vivo-pump',
    license='New BSD License',
    author='Michael Conlon',
    author_email='mconlon@duraspace.org',
    description='Use CSV files to update data in VIVO and get data from VIVO.  All semantics are externalized in'
        'JSON format definition files.',
    py_modules=['vivopump', 'pump'],
    requires=['rdflib(>=4.2.1)'],
)
