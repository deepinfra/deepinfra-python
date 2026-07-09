from setuptools import setup, find_packages

setup(
    name="deepinfra",
    version="0.1.0",
    author="Oguz Vuruskaner",
    author_email="oguzvuruskaner@gmail.com",
    description="Unofficial Python wrapper for the DeepInfra Inference API",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/deepinfra/deepinfra-python",
    packages=find_packages(),
    install_requires=[
        "requests",
    ],
    include_package_data=True,
    use_scm_version=True,
    setup_requires=["setuptools_scm"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
