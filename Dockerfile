FROM python:3.8
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz && \
  tar -xvzf ta-lib-0.4.0-src.tar.gz && \
  cd ta-lib/ && \
  ./configure --prefix=/usr && \
  make && \
  make install
RUN rm -R ta-lib ta-lib-0.4.0-src.tar.gz
COPY  requirements.txt  /requirements.txt
RUN pip install -r requirements.txt
COPY . .

# WORKDIR /app
# ADD requirements.txt .
# RUN pip install -r requirements.txt
CMD ["python","main.py"]
