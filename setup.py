#!/usr/bin/env python

from setuptools import setup

install_requires = [
    'boto3>=1.34.8',
]

setup(
    name='sentry-nodestore-s3',
    version='1.0.0',
    description='A Sentry plugin to add S3 as a NodeStore backend.',
    packages=['sentry_nodestore_s3'],
    install_requires=install_requires,
)
