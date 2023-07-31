# Cachito CLI

All you need to build packages and applications in an air-gapped environment.

## Features

Modules:
- Server: Install the Cachito server with all the components
- Builder: Build packages and applications in an air-gapped environment
- Nexus: Check repositories and packages

Additional features:
- Log system
- Python: Extract the `requirements.txt` from the Containerfile build using a proxy repository

Pending features:

- Configuration system via JSON/YAML
- Cachito: removed. Pending to be refactored


## How to use

Create a new cachito server:

```bash
# Create a new cachito server
# --clone-path: the parent path must exist, then the clone path will be created
mkdir -p /path/to/clone/cachito
./bin/cachito server start \
    --clone-path /path/to/clone/cachito/repo
```

When you want to stop the server, the following command will also clean the volumes:

```bash
./bin/cachito server stop \
    --clone-path /path/to/clone/cachito/repo
```

Create the `Containerfile`. It must contain the `#<cachito-disable>` and `#<cachito-proxy>` lines:

```dockerfile
# Containerfile
FROM docker.io/alpine:latest

#<cachito-disable>

# Here you have access to the internet and can install the main packages
RUN apk add py3-pip git
RUN git clone https://github.com/ansible/receptor.git /src/receptor

#<cachito-proxy>

# Here, you don't have access to the internet. The DNS resolution is disabled.
# You can use `pip` and `go mod` to install packages from the proxy repositories.
RUN pip install -U setuptools wheel
RUN pip install requests

# Create wheel
WORKDIR /src/receptor/receptorctl
RUN echo "0.0.1" > .VERSION
RUN mkdir /dist
RUN pip wheel --wheel-dir=/dist .
```

Build a package:

```bash
# Build a package
./bin/cachito builder build \
    -f ./path/to/Containerfile \
    -t my-image:latest

# Check the new created files
# (same path as the Containerfile)
cat ./path/to/cachito.containerfile
cat ./path/to/requirements.txt
```
