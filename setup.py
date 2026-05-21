from setuptools import setup, find_packages

setup(
    name="self-annealing",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "colorama>=0.4.6",
    ],
    entry_points={
        "console_scripts": [
            "anneal=self_annealing.cli:main",
        ],
    },
)
