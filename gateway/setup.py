from setuptools import setup, find_packages

setup(
    name="apple-health-export-gateway",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "grpcio>=1.62.0",
        "grpcio-tools>=1.62.0",
        "requests>=2.31.0",
        "protobuf>=4.25.0",
    ],
)