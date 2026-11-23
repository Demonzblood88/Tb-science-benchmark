#!/bin/bash
set -euo pipefail
cd /mnt/g/Tb-science-benchmark/authoring/upstream
git config http.version HTTP/1.1
git sparse-checkout set --no-cone --stdin < ../sparse_paths.txt
git checkout
git rev-parse HEAD
