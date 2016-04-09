from setuptools import setup

setup(
    name='ads',
    version='0.8.0',
    description='Start, stop, and manage microservices in a codebase',
    long_description=open('README.md').read(),  # TODO rst
    url='https://github.com/adamcath/ads',
    author='Adam Cath',
    author_email='adam.cath@gmail.com',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: MacOS X',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2.7',
        'Topic :: Utilities',
        'Topic :: Software Development'
    ],
    keywords='microservice tool launcher upstart init.d',
    packages=['ads'],
    install_requires=['pyyaml>=3.11'],
    entry_points={
        'console_scripts': ['ads=ads.__main__:main']
    }
)
