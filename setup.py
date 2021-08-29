#!/usr/bin/python3
from setuptools import setup

def readme():
    with open('README.md') as f:
        return f.read()

setup(
    name='Ocatune',
    version='0.1',
    description='Learn to play the ocarina in tune',
    long_description=readme(),
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
    ],
    keywords='ocarina tuner',
    url='https://github.com/robehickman/Ocatune',
    author='Robert Hickman',
    author_email='robehickman@gmail.com',
    license='MIT',
    install_requires=[
        'pyaudio', 'pygame', 'numpy'
    ],
    scripts=['ocatune.py'],
    zip_safe=False)

