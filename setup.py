from setuptools import find_packages, setup


with open("README.md", "r") as fh:
    long_description = fh.read()


dependencies = [l.strip() for l in open('requirements.txt')]

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
    install_requires=dependencies,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: BSD License",
        "Operating System :: MacOS",
        "Operating System :: POSIX",
    ],
)

