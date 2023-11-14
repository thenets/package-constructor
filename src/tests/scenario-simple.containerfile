FROM my.local/base-image

ADD constructor /constructor

ENV PIP_NO_BINARY=:all:

RUN set -x \
    && dnf install -y python3-pip \
    && python3 -m venv /venv \
    && /venv/bin/pip3 install -r /constructor/packagemanager/python/requirements-freeze.txt

RUN pip list -l > /hello.txt

CMD ["cat", "/hello.txt"]
