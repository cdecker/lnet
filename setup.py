import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="lnet",
    version="0.0.1",
    author="Christian Decker",
    author_email="decker.christian+pypi@gmail.com",
    description="Utilities to define and bootstrap lightning networks for testing",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/cdecker/lnet",
    packages=setuptools.find_packages(),
    scripts=['bin/lnet-cli', 'bin/lnet-daemon'],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: BSD License",
        "Operating System :: MacOS",
        "Operating System :: POSIX",
    ],
)
