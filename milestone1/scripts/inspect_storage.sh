#!/usr/bin/env bash
# Read-only discovery. No files are created, read for benchmarking, or modified.
set -u
if (( $# > 1 )); then
    printf 'Usage: bash scripts/inspect_storage.sh [EXISTING_DIRECTORY]\n' >&2
    exit 2
fi
printf '\nIdentity\n'
hostname
whoami
pwd
uname -srmo
printf '\nHome filesystem (not necessarily the test HDD)\n'
if command -v findmnt >/dev/null 2>&1; then
    findmnt -T "$HOME" -o TARGET,SOURCE,FSTYPE,OPTIONS || true
else
    df -hT "$HOME" || true
fi
printf '\nBlock devices (ROTA=1 normally indicates rotational storage)\n'
if command -v lsblk >/dev/null 2>&1; then
    lsblk -o NAME,TYPE,SIZE,ROTA,FSTYPE,MOUNTPOINTS 2>/dev/null ||
        lsblk -o NAME,TYPE,SIZE,ROTA,FSTYPE,MOUNTPOINT || true
else
    printf 'lsblk unavailable\n'
fi
printf '\nMounted filesystems\n'
if command -v findmnt >/dev/null 2>&1; then
    findmnt -rn -o TARGET,SOURCE,FSTYPE || true
fi
if (( $# == 1 )); then
    if [[ ! -d "$1" ]]; then
        printf 'Not an existing directory: %s\n' "$1" >&2
        exit 2
    fi
    candidate=$(cd -- "$1" && pwd -P) || exit 2
    printf '\nCandidate directory: %s\n' "$candidate"
    ls -ld -- "$candidate"
    df -hT -- "$candidate" || true
    if command -v findmnt >/dev/null 2>&1; then
        findmnt -T "$candidate" -o TARGET,SOURCE,FSTYPE,OPTIONS || true
    fi
    [[ -r "$candidate" ]] && printf 'Readable: yes\n' || printf 'Readable: no\n'
    [[ -w "$candidate" ]] && printf 'Writable: yes\n' || printf 'Writable: no\n'
    printf 'These permissions do not establish instructor approval or HDD placement.\n'
fi
printf '\nNext: confirm the team test directory and file-size allowance with Sheryar/instructor.\n'
