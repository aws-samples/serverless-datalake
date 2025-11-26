"""
Setup configuration for Document Insight Extraction System
"""
from setuptools import setup, find_packages

setup(
    name="document-insight-extraction",
    version="1.0.0",
    description="Serverless document processing and insight extraction system",
    author="AWS CDK",
    packages=find_packages(exclude=["tests*"]),
    install_requires=[
        "aws-cdk-lib==2.192.0",
        "constructs>=10.0.0,<11.0.0",
        "boto3>=1.34.0",
    ],
    python_requires=">=3.12",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.12",
    ],
)
