#!/usr/bin/env bash
# Run a solution on every input in inputs/ and zip the outputs for CMS.
#
#   ./run.sh cpp            compile and run code/solution.cpp
#   ./run.sh py             run code/solution.py
#   ./run.sh COMMAND...     run any command, e.g. ./run.sh java Solution
#   ./run.sh zip            only zip the files already in outputs/
#
# Set TESTS to run only some inputs, e.g. TESTS="00 03" ./run.sh cpp
# Outputs of the other inputs in outputs/ are kept.
set -u

dir="$(cd "$(dirname "$0")" && pwd)"
mode="${1:-}"

case "$mode" in
"")
    sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
    ;;
cpp)
    echo "Compiling code/solution.cpp"
    g++ -std=c++17 -O2 -o "$dir/code/solution" "$dir/code/solution.cpp" || exit 1
    cmd=("$dir/code/solution")
    ;;
py)
    if command -v python3 >/dev/null 2>&1; then
        cmd=(python3 "$dir/code/solution.py")
    else
        cmd=(python "$dir/code/solution.py")
    fi
    ;;
zip)
    cmd=()
    ;;
*)
    cmd=("$@")
    ;;
esac

mkdir -p "$dir/outputs"
failed=0
if [ "${#cmd[@]}" -gt 0 ]; then
    for input in "$dir"/inputs/input_*.txt; do
        name="$(basename "$input" .txt)"
        id="${name#input_}"
        if [ -n "${TESTS:-}" ] && [[ " $TESTS " != *" $id "* ]]; then
            continue
        fi
        echo "Running on $name.txt"
        if ! "${cmd[@]}" <"$input" >"$dir/outputs/output_$id.txt"; then
            echo "WARNING: the solution failed on $name.txt" >&2
            failed=1
        fi
    done
fi

rm -f "$dir/output.zip"
if ! ls "$dir"/outputs/output_*.txt >/dev/null 2>&1; then
    echo "No files in outputs/ to zip." >&2
    exit 1
fi
if command -v zip >/dev/null 2>&1; then
    (cd "$dir/outputs" && zip -q "$dir/output.zip" output_*.txt)
elif command -v python3 >/dev/null 2>&1; then
    (cd "$dir/outputs" && python3 -m zipfile -c "$dir/output.zip" output_*.txt)
else
    echo "Install zip or python3, or zip outputs/output_*.txt yourself." >&2
    exit 1
fi
echo "Created output.zip. Submit it in CMS."
exit "$failed"
