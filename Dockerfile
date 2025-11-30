# =============================================================================
# Stage 1: Base system setup
# =============================================================================
FROM ubuntu:20.04 AS base
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y \
    build-essential \
    wget \
    gcc \
    make \
    libncurses5-dev \
    libncursesw5-dev \
    autotools-dev \
    automake \
    autoconf \
    libtool \
    nano \
    libc6-dbg \
    grep \
    libarchive-tools \
    gfortran \
    python-is-python3 \
    python3-venv \
    pip \
    && rm -rf /var/lib/apt/lists/* \
    && pip install tqdm

# =============================================================================
# Stage 2: SPEC CPU2017 installation
# =============================================================================
FROM base AS spec-builder
COPY cpu2017-1.1.9.iso /opt/spec/cpu2017.iso
RUN mkdir -p /usr/cpu2017 \
    && bsdtar -C /usr/cpu2017 -xf /opt/spec/cpu2017.iso \
    && chmod +x /usr/cpu2017/install.sh \
    && echo -e "/usr/cpu2017\nyes" | /usr/cpu2017/install.sh \
    && rm /opt/spec/cpu2017.iso

# =============================================================================
# Stage 3: Test programs build
# =============================================================================
FROM base AS test-builder
COPY alloc.c /tmp/alloc.c
RUN gcc -mavx -mavx2 -O0 -g -o /tmp/alloc /tmp/alloc.c

# =============================================================================
# Stage 4: Valgrind custom build
# =============================================================================
FROM base AS valgrind-builder
ADD valgrind /opt/valgrind
WORKDIR /opt/valgrind
RUN sed -i -e 's/\r$//' autogen.sh && find . -type f -exec sed -i -e 's/\r$//' {} \; \
    && chmod +x ./auxprogs/* \
    && chmod +x autogen.sh \
    && ./autogen.sh \
    && ./configure --prefix=/opt/valgrind/inst \
    && make install

# =============================================================================
# Stage 5: Final runtime image
# =============================================================================
FROM base AS runtime
ENV DEBIAN_FRONTEND=noninteractive

# Copy SPEC CPU2017 from builder stage
COPY --from=spec-builder /usr/cpu2017 /usr/cpu2017

# Copy custom Valgrind from builder stage
COPY --from=valgrind-builder /opt/valgrind/inst /opt/valgrind/inst
ENV PATH="/opt/valgrind/inst/bin:${PATH}"

# Copy test programs from builder stage
COPY --from=test-builder /tmp/alloc /usr/alloc

# Copy SPEC config
COPY spec/memlog-monitor.cfg /usr/cpu2017/config/memlog-monitor.cfg
RUN sed -i 's/\r$//' /usr/cpu2017/config/memlog-monitor.cfg

# Copy and setup menu
COPY menu.sh /usr/local/bin/menu.sh
RUN sed -i 's/\r$//' /usr/local/bin/menu.sh \
    && chmod +x /usr/local/bin/menu.sh

# Copy analyze script
COPY analyze.sh /usr/local/bin/analyze.sh
RUN sed -i 's/\r$//' /usr/local/bin/analyze.sh \
    && chmod +x /usr/local/bin/analyze.sh

# Copy parser
COPY parser.py /usr/parser.py
RUN sed -i 's/\r$//' /usr/parser.py \
    && chmod +x /usr/parser.py

# Set working directory
WORKDIR /workspace

# Run menu on container init
CMD ["/usr/local/bin/menu.sh"]
