from setuptools import setup

setup(
    name='todo-webapp',
    packages=['task'],
    include_package_data=True,
    install_requires=[
        'flask',
        'pysqlite3'
    ],
)