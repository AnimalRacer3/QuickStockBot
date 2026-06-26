#!/bin/bash
# Downloads Prisma engine binaries via proxy if needed, then runs prisma generate.
set -e

ENGINES_VERSION=$(node -e "console.log(require('./node_modules/@prisma/engines-version').enginesVersion)" 2>/dev/null)
ENGINES_DIR="node_modules/@prisma/engines"
PRISMA_DIR="node_modules/prisma"
PLATFORM="debian-openssl-3.0.x"
BASE_URL="https://binaries.prisma.sh/all_commits/${ENGINES_VERSION}/${PLATFORM}"

download_if_missing() {
  local name="$1"
  local dest="$2"
  if [ ! -f "$dest" ]; then
    echo "Downloading $name..."
    PROXY_ARGS=""
    if [ -n "${HTTPS_PROXY:-}" ]; then
      PROXY_ARGS="--proxy ${HTTPS_PROXY}"
    fi
    CA_ARGS=""
    if [ -n "${NODE_EXTRA_CA_CERTS:-}" ]; then
      CA_ARGS="--cacert ${NODE_EXTRA_CA_CERTS}"
    fi
    curl --connect-timeout 30 --max-time 300 -sL $PROXY_ARGS $CA_ARGS "${BASE_URL}/${name}.gz" | gunzip > "$dest"
    chmod +x "$dest"
  fi
}

download_if_missing "schema-engine"           "${ENGINES_DIR}/schema-engine-${PLATFORM}"
download_if_missing "libquery_engine.so.node" "${ENGINES_DIR}/libquery_engine-${PLATFORM}.so.node"
download_if_missing "libquery_engine.so.node" "${PRISMA_DIR}/libquery_engine-${PLATFORM}.so.node"

CHECKPOINT_DISABLE=1 node node_modules/prisma/build/index.js generate
