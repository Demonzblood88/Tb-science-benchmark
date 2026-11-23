#!/bin/bash
set -eu
export PATH="$HOME/.local/bin:$PATH"
printf '%s\n' '--- downloads ---'
ps -eo pid,etime,args | grep -E 'git (fetch|checkout|sparse)|fetch_references' || true
du -sh /mnt/g/Tb-science-benchmark/authoring/upstream/.git/objects
printf '%s\n' '--- Docker ---'
docker version
printf '%s\n' '--- Harbor ---'
harbor --version
