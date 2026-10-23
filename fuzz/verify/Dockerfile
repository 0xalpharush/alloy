ARG BASE_BUILDER=alloy-verify-builder
FROM ${BASE_BUILDER}
COPY . /src/alloy
RUN uv run --no-project python /src/alloy/fuzz/verify/prepare.py \
      --source /src/alloy --work /work \
      --adapter /usr/local/lib/oss-verify/rust
COPY fuzz/verify/build.sh /src/build.sh
WORKDIR /src/alloy
