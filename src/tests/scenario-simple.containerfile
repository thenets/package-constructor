FROM my.local/base-image

ADD constructor /constructor

ENV PIP_NO_BINARY=:all:

RUN set -x \
    && source constructor/proxy/main/proxy.sh \
    && python3 -m venv /venv \
    && /venv/bin/pip3 install -r /constructor/packagemanager/python/requirements-freeze.txt

RUN pip list -l > /hello.txt

CMD ["cat", "/hello.txt"]
