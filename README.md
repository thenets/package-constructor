# Package Constructor

All you need to build packages and applications in an air-gapped environment. The power of `cachito` and `podman` combined.

## Why was this project created?

- My pain: it takes too long to iterate in an air-gapped Jenkins or any other pipeline. The flow of committing to a git repo and triggering a job in a CI tool it's not a productive solution.

- My problem: I need a faster way to iterate and build a container, a portion with internet access and a portion without internet access. I also need to extract all Python dependencies downloaded, including the hidden ones, like `build`, `hatch`, `hacther`, etc.

- The goal of this project: build a container image with a section with internet and another without internet + using Cachito proxies. It also extracts all Python dependencies that passed
through the Cachito proxy (Nexus pip proxy repo).

- Result: this way, I can iterate fast and retrieve dependencies that `pip freeze` don't return.

## Features

Main features:
- Build system configurable via a single YAML file

Modules:
- Server: Install the Cachito server with all the components
- Builder: Build packages and applications in an air-gapped environment
- Nexus: Check repositories and packages

Additional features:
- Python: Extract the `requirements.txt` from the Containerfile build using a proxy repository

Pending features/tasks:
- [ ] Automatically extract Python depenedencies based on the configuration file
- [ ] Create new proxy pip repos per build instead of restart cachito and cleanup the cache
- [ ] Each `Dockerfile` should be built with their own context. So, for all files from it's location must be copied to the workdir


## How to use

Add the `./bin/` to your `$PATH` var:

```bash
export $PATH=$(pwd)/bin/:${PATH}
```

Start all Cachito servers:

```bash
constructor
```

Create the `./Containerfile`. In order to use the internal Cachito servers you must load `constructor/proxy/<imageName>/proxy.sh` to your context:

```dockerfile
# ./Containerfile
FROM my.local/base-image

ADD constructor /constructor

ENV PIP_NO_BINARY=:all:

RUN set -x \
    && source constructor/proxy/main/proxy.sh \
    && python3 -m venv /venv \
    && /venv/bin/pip3 install -r /constructor/packagemanager/python/requirements-freeze.txt

RUN pip list -l > /hello.txt

CMD ["cat", "/hello.txt"]
```

Create the main configuration file:

```yaml
# Simplest scenario for the Package Constructor build system
# - Container build

---

# Defines the container build
kind: container

# Defines the working directory where the constructor will be executed
# and will store all the generated files
workdir:
  # Path to the working directory relative to the configuration file
  path: ./cache/

# Each source will be cloned into a volume
# and then added to the container build
sources:
  - kind: git
    url: https://github.com/pyca/cryptography.git
    ref: "41.0.5"
    path: cryptography

# Each package manager will have a respective proxy service available
# for the container build
packageManagers:
  # Ansible roles and collections
  # creates the files:
  #   $WORKDIR/constructor/packagemanager/ansible/requirements.yml
  #   $WORKDIR/constructor/packagemanager/ansible/requirements-freeze.txt
  ansible:
    # Collections. Must include the package name and version
    collections:
      - community-general==6.2.0
    # Roles. Must include the package name and version
    roles:
      - cloudalchemy.node_exporter==2.0.0

  # Python package manager
  # creates the file $WORKDIR/constructor/packagemanager/python/requirements-freeze.txt
  python:
    pythonVersion: "^3.9"
    # If true, it will search for all the dependencies to build the package
    includeDependencies: true
    # Dependencies. Must include the package name and version
    dependencies:
      - cryptography==41.0.5

# Assuming "kind: containers", the container key is required
# Each container will be built sequentially. You can chain them.
containers:
  # Base image
  # ===================
  - name: "base"
    imageName: "my.local/base-image"
    containerfileContent: |
      FROM docker.io/redhat/ubi9:latest
      RUN set x \
          && dnf install -y \
              # utils
              tar vim bash findutils dnf \
              # rust
              cargo \
              # gcc
              gcc gcc-c++ cmake cmake-data \
              # cryptography
              libffi-devel openssl-devel redhat-rpm-config pkg-config \
              # python
              python3-devel \
              python3-pip-wheel \
              python3-setuptools \
              python3-setuptools-wheel \
              python3-wheel-wheel \
              python3-six
    restrictions:
      disableDnsResolution: false
    proxies:
      python: false
      golang: false
    sources_subpath: sources
    podmanCacheEnabled: true


  # Main image
  # ===================
  - # Build name (required, must be unique, [a-z, 0-9, -])
    name: "main"

    # Podman image name (required)
    imageName: "package-constructor-scenario-simple"

    # Main Containerfile (required)
    # This is where the main logic of the container build is defined
    containerfilePath: ./scenario-simple.containerfile

    # All restrictions applied during the build time
    # if a build can be performed in a container with these restrictions
    # it probably means that all the dependencies can be compiled in an
    # air-gapped environment.
    restrictions:
      disableDnsResolution: true

    # All proxies applied during the build time
    # in order to enable them, you must source the proxy file
    # example:
    #   COPY constructor/proxy.sh /tmp/proxy.sh
    #   RUN source /tmp/proxy.sh && pip install requests
    proxies:
      python: true
      golang: true

    # Sources subpath (default: sources)
    # Available in the container build context
    # Example: COPY sources /tmp/sources
    sources_subpath: sources

    # Cache enabled (default: true)
    podmanCacheEnabled: false
```

## FAQ

- Is this solution too focused on Python packaging?
  Yes. There are probably design issues in how I architected the `cli_builder.py` module.

- How do you deal with third-party bindings like `C`, `C++` or `Rust`?
  I don't. All binding dependencies must come from the distro's package manager. For `Rust` specifically, none is supported since `cachito` don't yet support it, so you must vendor their lib, read more here at [cargo-vendor](https://doc.rust-lang.org/cargo/commands/cargo-vendor.html).
