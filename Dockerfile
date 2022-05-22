FROM python:3.8
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz && \
  tar -xvzf ta-lib-0.4.0-src.tar.gz && \
  cd ta-lib/ && \
  ./configure --prefix=/usr && \
  make && \
  make install
RUN rm -R ta-lib ta-lib-0.4.0-src.tar.gz
# copy the dependencies file to the working directory
COPY  requirements.txt  /requirements.txt
# install dependencies
RUN pip install -r requirements.txt

# copy the content of the local src directory to the working directory
COPY . .

# WORKDIR /app
# ADD requirements.txt .
# RUN pip install -r requirements.txt
CMD ["python","main.py"]


