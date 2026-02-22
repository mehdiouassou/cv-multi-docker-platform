from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="symphony-cv-platform",
    version="1.0.0",
    author="Mehdi Ouassou",
    description="Piattaforma Multi-Docker per Algoritmi di Computer Vision",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    install_requires=[
        "fastapi>=0.100.0",
        "uvicorn>=0.20.0",
        "docker>=6.1.0",
        "pydantic>=2.0.0",
        "PyYAML>=6.0",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
)
