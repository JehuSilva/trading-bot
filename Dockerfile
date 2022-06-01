# syntax=docker/dockerfile:1
# Python base
FROM python:3.10

# Ensure logging is set up correctly
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1


# Installing 
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz && \
    tar -xzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib/ && \
    ./configure --prefix=/usr && \
    make && \
    make install

# Upgrading pip 
RUN python3 -m pip install --upgrade pip

# Set up the project directory
WORKDIR /opt/app/

# Install python packages
COPY app/requirements.txt /opt/app/
RUN pip3 install -r requirements.txt

COPY app/ /opt/app/


CMD ["python3","main.py"]


