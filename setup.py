from setuptools import find_packages, setup


with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="lnet",
    version="0.0.4",
    author="Christian Decker",
    author_email="decker.christian+pypi@gmail.com",
    description="Utilities to define and bootstrap lightning networks for testing",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/cdecker/lnet",
    packages=['lnet'],
    scripts=['bin/lnet-cli', 'bin/lnet-daemon'],
    install_requires=[
        "click==7.0",
        "pylightning==0.0.4",
        "pydot==1.2.4",
        "python-bitcoinlib==0.7.0",
        "ephemeral-port-reserve==1.1.0",
        "python-daemon==2.2.0",
        "filelock==3.0.9",
        "flask==1.0.2",
        "flask-jsonrpc==0.3.1",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: BSD License",
        "Operating System :: MacOS",
        "Operating System :: POSIX",
    ],
)

