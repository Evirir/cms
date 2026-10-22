#!/usr/bin/env bash
# Run a solution on every input in inputs/ and zip the outputs for CMS.
#
#   ./run.sh LANGUAGE       compile and run code/solution.* (Solution.java), where
#                           LANGUAGE is cpp, c, py, java, cs, rs, php, hs or pas
#   ./run.sh COMMAND...     run any command, e.g. ./run.sh node code/solution.js
#   ./run.sh zip            only zip the files already in outputs/
#
# Set CXX (cpp) or CC (c) to choose a compiler. Set TESTS to run only some
# inputs, e.g. TESTS="sample_01 03" ./run.sh cpp; outputs of the other inputs
# in outputs/ are kept. No compiler? See README.md.
set -u

dir="$(cd "$(dirname "$0")" && pwd)"
inputs_dir="$dir/inputs"
outputs_dir="$dir/outputs"
zip_file="$dir/output.zip"
in_prefix="in_"
out_prefix="out_"
code_dir="$dir/code"
binary="$code_dir/solution"
# Same flags as the CMS languages. macOS can't link statically.
cxxflags=(-DEVAL -std=gnu++20 -O2 -pipe)
cflags=(-DEVAL -std=gnu11 -O2 -pipe)
fpcflags=(-dEVAL -O2)
if [ "$(uname -s)" != Darwin ]; then
    cxxflags+=(-static -s)
    cflags+=(-static -s)
    fpcflags+=(-XSs)
fi
mode="${1:-}"
source=""

# Print the first of the given commands that is installed.
first_command() {
    local candidate
    for candidate in "$@"; do
        if command -v "$candidate" >/dev/null 2>&1; then
            echo "$candidate"
            return 0
        fi
    done
    return 1
}

# Exit, explaining that the tool for $1 (e.g. "C++ compiler") is missing.
# $2 is how to get it.
missing() {
    echo "No $1 found. $2" >&2
    if [ -n "${source:-}" ]; then
        echo "Or compile ${source#"$dir/"} yourself, e.g. in your IDE, then run:" >&2
        echo "./run.sh path/to/your/program" >&2
    fi
    exit 1
}

# Print what is compiled, then run the compile command, exiting if it fails.
compile() {
    echo "Compiling ${source#"$dir/"} with $1"
    "$@" || exit 1
}

case "$mode" in
"")
    sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
    ;;
cpp)
    source="$code_dir/solution.cpp"
    cxx="${CXX:-$(first_command g++ clang++)}"
    command -v "$cxx" >/dev/null 2>&1 ||
        missing "C++ compiler" "Set CXX to yours: CXX=/path/to/g++ ./run.sh cpp"
    compile "$cxx" "${cxxflags[@]}" -o "$binary" "$source"
    cmd=("$binary")
    ;;
c)
    source="$code_dir/solution.c"
    cc="${CC:-$(first_command gcc clang)}"
    command -v "$cc" >/dev/null 2>&1 ||
        missing "C compiler" "Set CC to yours: CC=/path/to/gcc ./run.sh c"
    compile "$cc" "${cflags[@]}" -o "$binary" "$source" -lm
    cmd=("$binary")
    ;;
py)
    python="$(first_command python3 python)" ||
        missing "Python" "Install Python 3 from https://www.python.org"
    cmd=("$python" "$code_dir/solution.py")
    ;;
java)
    source="$code_dir/Solution.java"
    command -v javac >/dev/null 2>&1 ||
        missing "Java compiler (javac)" "Install a JDK, e.g. from https://adoptium.net"
    compile javac -d "$code_dir" "$source"
    cmd=(java -Deval=true -Xss64M -cp "$code_dir" Solution)
    ;;
cs)
    source="$code_dir/solution.cs"
    command -v mcs >/dev/null 2>&1 ||
        missing "C# compiler (mcs)" "Install Mono from https://www.mono-project.com"
    compile mcs -out:"$binary.exe" -optimize+ "$source"
    cmd=(mono "$binary.exe")
    ;;
rs)
    source="$code_dir/solution.rs"
    command -v rustc >/dev/null 2>&1 ||
        missing "Rust compiler (rustc)" "Install Rust from https://rustup.rs"
    compile rustc -O -o "$binary" "$source"
    cmd=("$binary")
    ;;
php)
    command -v php >/dev/null 2>&1 ||
        missing "PHP" "Install PHP from https://www.php.net"
    cmd=(php -d memory_limit=-1 "$code_dir/solution.php")
    ;;
hs)
    source="$code_dir/solution.hs"
    command -v ghc >/dev/null 2>&1 ||
        missing "Haskell compiler (ghc)" "Install GHC from https://www.haskell.org/ghcup"
    compile ghc -O2 -o "$binary" "$source"
    cmd=("$binary")
    ;;
pas)
    source="$code_dir/solution.pas"
    command -v fpc >/dev/null 2>&1 ||
        missing "Pascal compiler (fpc)" "Install Free Pascal from https://www.freepascal.org"
    compile fpc "${fpcflags[@]}" -o"$binary" "$source"
    cmd=("$binary")
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
    for input in "$inputs_dir/sample_$in_prefix"*.txt "$inputs_dir/$in_prefix"*.txt; do
        [ -e "$input" ] || continue
        # in_01 -> 01, sample_in_01 -> sample_01
        name="$(basename "$input" .txt)"
        id="${name/"$in_prefix"/}"
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
