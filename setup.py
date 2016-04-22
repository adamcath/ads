from setuptools import setup

try:
    long_description = open('build/README.rst').read()
except IOError:
    long_description = "Generated README.rst not found. " \
                       "Please run from publish.sh"

setup(
    name='adscli',
    version='0.8.6',
    description='Start, stop, and manage microservices in a codebase',
    long_description=long_description,
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
    license='MIT',
    packages=['ads'],
    install_requires=['pyyaml>=3.11'],
    entry_points={
        'console_scripts': ['ads=ads.__main__:main']
    }
)
