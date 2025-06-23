FROM debian/snapshot:bookworm-20220316

RUN apt-get update --fix-missing && \
    apt-get install -y wget bzip2 ca-certificates curl git && \
    apt-get clean

RUN apt-get update && \
    apt-get install -y build-essential libssl-dev libffi-dev \
    python3.10 python3.10-dev python3.10-venv python3-pip && \
    ln -sf /usr/bin/python3.10 /usr/bin/python3 && \
    ln -sf /usr/bin/python3.10 /usr/bin/python

RUN apt-get update && apt-get install -y \
    binutils libproj-dev gdal-bin python3-gdal libglib2.0-0 libsm6 libxext6 libxrender-dev \
    procps xmlsec1 libsasl2-dev libgdal-dev pdal libpdal-dev \
    postgresql postgresql-contrib libgeos-dev gfortran apt-utils cmake libpython3-dev

RUN apt-get install -y tini
ENTRYPOINT [ "/usr/bin/tini", "--" ]

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

# Set up virtual environment
RUN python3.10 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip, install build tools
RUN pip install --upgrade pip setuptools wheel cython

COPY requirements.txt /usr/src/app/

# Install dependencies - use fallback if necessary
RUN pip install -r requirements.txt
# RUN pip install --no-use-pep517 -r requirements.txt

COPY . /usr/src/app

EXPOSE 8000
CMD ["gunicorn", "webserver.wsgi", "-b", "0.0.0.0", "-w", "6"]