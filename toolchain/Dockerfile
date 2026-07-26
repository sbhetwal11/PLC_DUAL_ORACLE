# Reproducible verification toolchain: MATIEC (iec2c) + nuXmv + Python.
# Builds the SAME environment on this laptop and on the Vast.ai 5090 box.
#
# Build:  docker build -t plcbench-tc ./toolchain
# Run  :  docker run --rm -it -v "$PWD":/work -w /work plcbench-tc bash
# Then :  python3 -m plcbench.cli check-tools   (should show MATIEC + nuXmv available)
#
# NOTE on nuXmv: its license requires manual download. Get the Linux tarball from
# https://nuxmv.fbk.eu/ and place it as  toolchain/nuXmv.tar.gz  before building.
# (NuSMV is fully open if you prefer; adjust below.)

FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential flex bison autoconf automake libtool \
        git ca-certificates python3 python3-pip python3-venv xz-utils \
    && rm -rf /var/lib/apt/lists/*

# --- MATIEC (IEC 61131-3 -> C compiler; provides iec2c) ---------------------
# ARG lets you swap the source mirror if needed.
ARG MATIEC_GIT=https://github.com/nucleron/matiec.git
RUN ( git clone --depth 1 ${MATIEC_GIT} /opt/matiec \
      && cd /opt/matiec && autoreconf -i && ./configure && make -j"$(nproc)" \
      && ln -sf /opt/matiec/iec2c /usr/local/bin/iec2c ) \
    || echo "WARNING: MATIEC build failed; compile-check disabled (nuXmv verification still works)"
ENV MATIEC_IEC2C=/usr/local/bin/iec2c

# --- nuXmv (model checker) --------------------------------------------------
# Expects toolchain/nuXmv.tar.xz (downloaded manually per license; v2.2.0 layout
# extracts usr/local/bin/nuXmv, so strip-components=1 into / lands it on PATH).
COPY nuXmv.tar.xz /tmp/nuXmv.tar.xz
RUN tar -xf /tmp/nuXmv.tar.xz -C / --strip-components=1 \
    && chmod +x /usr/local/bin/nuXmv \
    && rm -f /tmp/nuXmv.tar.xz
ENV NUXMV_BIN=/usr/local/bin/nuXmv

# --- Python deps for the harness -------------------------------------------
RUN pip3 install --no-cache-dir pydantic>=2.7 pytest>=8.0

WORKDIR /work
CMD ["bash"]
