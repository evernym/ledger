# Development
FROM ubuntu:16.04

# Install environment
RUN apt-get update -y
RUN apt-get install -y git
RUN apt-get install -y wget
RUN apt-get install -y python3.5
RUN apt-get install curl
RUN curl "https://bootstrap.pypa.io/get-pip.py" -o "get-pip.py"
RUN /usr/lib/python3 get-pip.py
RUN pip3 install -U pip
RUN pip3 install -U setuptools
RUN pip3 install virtualenv