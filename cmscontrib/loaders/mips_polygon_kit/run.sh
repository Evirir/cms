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
inputs_dir="$dir/inputs"
outputs_dir="$dir/outputs"
zip_file="$dir/output.zip"
in_prefix="input_"
out_prefix="output_"
cpp_source="$dir/code/solution.cpp"
cpp_binary="$dir/code/solution"
py_source="$dir/code/solution.py"
# Same flags as the CMS "C++20 / g++" language. macOS can't link statically.
cxxflags=(-DEVAL -std=gnu++20 -O2 -pipe)
[ "$(uname -s)" = Darwin ] || cxxflags+=(-static -s)
mode="${1:-}"

case "$mode" in
"")
    sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
    ;;
cpp)
    echo "Compiling code/solution.cpp"
    g++ "${cxxflags[@]}" -o "$cpp_binary" "$cpp_source" || exit 1
    cmd=("$cpp_binary")
    ;;
py)
    if command -v python3 >/dev/null 2>&1; then
        cmd=(python3 "$py_source")
    else
        cmd=(python "$py_source")
    fi
    ;;
zip)
    cmd=()
    ;;
*)
    cmd=("$@")
    ;;
esac

mkdir -p "$outputs_dir"
failed=0
if [ "${#cmd[@]}" -gt 0 ]; then
    for input in "$inputs_dir/$in_prefix"*.txt; do
        name="$(basename "$input" .txt)"
        id="${name#"$in_prefix"}"
        if [ -n "${TESTS:-}" ] && [[ " $TESTS " != *" $id "* ]]; then
            continue
        fi
        echo "Running on $name.txt"
        if ! "${cmd[@]}" <"$input" >"$outputs_dir/$out_prefix$id.txt"; then
            echo "WARNING: the solution failed on $name.txt" >&2
            failed=1
        fi
    done
fi

rm -f "$zip_file"
if ! ls "$outputs_dir/$out_prefix"*.txt >/dev/null 2>&1; then
    echo "No files in outputs/ to zip." >&2
    exit 1
fi
if command -v zip >/dev/null 2>&1; then
    (cd "$outputs_dir" && zip -q "$zip_file" "$out_prefix"*.txt)
elif command -v python3 >/dev/null 2>&1; then
    (cd "$outputs_dir" && python3 -m zipfile -c "$zip_file" "$out_prefix"*.txt)
else
    echo "Install zip or python3, or zip outputs/$out_prefix*.txt yourself." >&2
    exit 1
fi
echo "Created output.zip. Submit it in CMS."
exit "$failed"
