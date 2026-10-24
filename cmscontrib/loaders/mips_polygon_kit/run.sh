#!/usr/bin/env bash
# Run a solution on every input in inputs/ and zip the outputs for CMS.
#
#   ./run.sh LANGUAGE       compile and run code/solution.* (Solution.java), where
#                           LANGUAGE is cpp, c, py, java, cs, rs, php, hs or pas
#   ./run.sh COMMAND...     run any command, e.g. ./run.sh node code/solution.js
#   ./run.sh zip            only zip the files already in outputs/
#
# Options, before LANGUAGE or COMMAND:
#   --tests in_01.txt sample_in_02.txt ...   run only on these inputs
#   --timeout 10                             stop and skip an input after 10 s
#   --std 17                                 cpp and c: compile as C++17 (gnu++17
#                                            if the compiler has it), or e.g.
#                                            --std c++17, --std gnu++17, --std c99
#   e.g. ./run.sh --tests in_01.txt in_03.txt --timeout 10 cpp
#
# Each run saves its answers and log.txt in runs/<date>_<time>/. Answers that
# finished without crashing or timing out are copied to outputs/, which keeps
# the latest good answer of every input and is zipped into output.zip.
# Without --std, cpp and c use the newest standard up to the one CMS uses
# (gnu++20, gnu11) that the compiler has.
# Set CXX (cpp) or CC (c) to choose a compiler. No compiler? See README.md.
set -u

dir="$(cd "$(dirname "$0")" && pwd)"
inputs_dir="$dir/inputs"
outputs_dir="$dir/outputs"
runs_dir="$dir/runs"
zip_file="$dir/output.zip"
in_prefix="in_"
out_prefix="out_"
code_dir="$dir/code"
binary="$code_dir/solution"
# Same flags as the CMS languages, which use C++20 and C11. -std is added
# later. macOS can't link statically.
cms_cxx_std=20
cms_c_std=11
cxxflags=(-DEVAL -O2 -pipe)
cflags=(-DEVAL -O2 -pipe)
fpcflags=(-dEVAL -O2)
if [ "$(uname -s)" != Darwin ]; then
    cxxflags+=(-static -s)
    cflags+=(-static -s)
    fpcflags+=(-XSs)
fi
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

# Print the comment at the top of this file.
usage() {
    awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"
}

# Print the name of input $1 without .txt, e.g. in_01 for in_01.txt,
# inputs/in_01.txt, in_01 or 01, and sample_in_01 for sample_01.
# Returns 1 if there is no such input, 2 if $1 doesn't look like an input.
input_file() {
    local name="${1##*/}" file looks="^(sample_|$in_prefix)|^[0-9]+$"
    name="${name##*\\}"
    case "$name" in
    *.txt) name="${name%.txt}" ;;
    *.*) return 2 ;;
    esac
    case "$name" in
    sample_"$in_prefix"* | "$in_prefix"*) file="$name" ;;
    sample_*) file="sample_$in_prefix${name#sample_}" ;;
    *) file="$in_prefix$name" ;;
    esac
    if [ -e "$inputs_dir/$file.txt" ]; then
        echo "$file"
        return 0
    fi
    if [[ "$1" == *.txt || "$1" == *inputs[/\\]* || "$name" =~ $looks ]]; then
        return 1
    fi
    return 2
}

# Print the other name of C++ ($1 is c++) or C ($1 is c) standard $2, e.g.
# 2a for 20, which compilers that are too old for the final name know.
std_alias() {
    case "$1 $2" in
    "c++ 23") echo 2b ;;
    "c++ 20") echo 2a ;;
    "c++ 17") echo 1z ;;
    "c++ 14") echo 1y ;;
    "c++ 11") echo 0x ;;
    "c 11") echo 1x ;;
    "c 99") echo 9x ;;
    esac
}

# Print the -std values to try for language $1 (c++ or c), best first: the
# ones for --std $2, or with no $2 the CMS standard and then older ones.
# GNU (gnu++17) comes before standard (c++17) unless $2 asks for c++/c.
std_candidates() {
    local language="$1" choice="$2" gnu="gnu${1#c}" versions version kind=gnu
    if [ -z "$choice" ]; then
        if [ "$language" = c++ ]; then
            versions="20 2a 17 1z 14 1y 11 0x"
        else
            versions="11 1x 99 9x"
        fi
    else
        version="${choice#gnu}"
        if [ "$version" = "$choice" ] && [ "${choice#c}" != "$choice" ]; then
            kind=standard
            version="${choice#c}"
        fi
        version="${version#++}"
        versions="$version $(std_alias "$language" "$version")"
    fi
    for version in $versions; do
        if [ "$kind" = gnu ]; then
            echo "$gnu$version"
        fi
        echo "$language$version"
    done
}

# Print the first of -std values $3... that compiler $1 accepts for language
# $2 (c++ or c).
first_std() {
    local compiler="$1" language="$2" std
    shift 2
    for std in "$@"; do
        if "$compiler" -std="$std" -x "$language" -fsyntax-only - \
            </dev/null >/dev/null 2>&1; then
            echo "$std"
            return 0
        fi
    done
    return 1
}

# Set std_flag to -std=... for compiler $1, language $2 (c++ or c) and the
# CMS standard $3: --std, or the best standard the compiler has.
std_flag=""
pick_std() {
    local -a candidates
    local std name="C" example=99 cms
    if [ "$2" = c++ ]; then
        name="C++"
        example=17
    fi
    candidates=($(std_candidates "$2" "$std_choice"))
    if ! std="$(first_std "$1" "$2" "${candidates[@]}")"; then
        if [ -n "$std_choice" ]; then
            echo "$1 doesn't know --std $std_choice. Try an older standard," \
                "e.g. --std $example, or a newer compiler." >&2
            exit 1
        fi
        echo "WARNING: $1 doesn't know $name$3 or older standards, so compiling" \
            "without -std." >&2
        return
    fi
    std_flag="-std=$std"
    cms=" $(std_candidates "$2" "$3" | tr '\n' ' ') "
    if [ -z "$std_choice" ] && [[ "$cms" != *" $std "* ]]; then
        echo "WARNING: $1 doesn't know $name$3, which CMS uses, so compiling with" \
            "-std=$std. If your code needs $name$3, use a newer compiler." >&2
    fi
}

# Print what is compiled, then run the compile command, exiting if it fails.
compile() {
    echo "Compiling ${source#"$dir/"} with $1${std_flag:+ $std_flag}"
    "$@" || exit 1
}

tests=""
limit=""
std_choice=""
while [ $# -gt 0 ]; do
    case "$1" in
    --tests)
        shift
        found=0
        while [ $# -gt 0 ]; do
            file="$(input_file "$1")"
            case $? in
            0)
                tests="$tests $file.txt"
                found=1
                shift
                ;;
            1)
                echo "No input named $1 in inputs/" >&2
                exit 1
                ;;
            *) break ;;
            esac
        done
        if [ "$found" -eq 0 ]; then
            echo "--tests needs input names, e.g. --tests in_01.txt in_03.txt" >&2
            exit 1
        fi
        ;;
    --timeout)
        if [ $# -lt 2 ] || ! [[ "$2" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
            echo "--timeout needs a number of seconds, e.g. --timeout 10" >&2
            exit 1
        fi
        limit="$2"
        shift 2
        ;;
    --std)
        if [ $# -lt 2 ] || ! [[ "$2" =~ ^(gnu|c)?(\+\+)?[0-9][0-9a-z]$ ]]; then
            echo "--std needs a C++ or C standard, e.g. --std 17, --std c++17," \
                "--std gnu++17 or --std c99" >&2
            exit 1
        fi
        std_choice="$2"
        shift 2
        ;;
    -h | --help)
        usage
        exit 0
        ;;
    -*)
        echo "Unknown option $1. The options are --tests, --timeout and --std." >&2
        exit 1
        ;;
    *) break ;;
    esac
done
tests="${tests# }"
if [[ "$limit" =~ ^0*([.]0*)?$ ]]; then
    limit=""
fi
mode="${1:-}"
if [ -n "$std_choice" ] && [ "$mode" != cpp ] && [ "$mode" != c ]; then
    echo "--std only works with cpp and c." >&2
    exit 1
fi

case "$mode" in
"")
    usage
    exit 1
    ;;
cpp)
    source="$code_dir/solution.cpp"
    cxx="${CXX:-$(first_command g++ clang++)}"
    command -v "$cxx" >/dev/null 2>&1 ||
        missing "C++ compiler" "Set CXX to yours: CXX=/path/to/g++ ./run.sh cpp"
    pick_std "$cxx" c++ "$cms_cxx_std"
    compile "$cxx" ${std_flag:+"$std_flag"} "${cxxflags[@]}" -o "$binary" "$source"
    cmd=("$binary")
    ;;
c)
    source="$code_dir/solution.c"
    cc="${CC:-$(first_command gcc clang)}"
    command -v "$cc" >/dev/null 2>&1 ||
        missing "C compiler" "Set CC to yours: CC=/path/to/gcc ./run.sh c"
    pick_std "$cc" c "$cms_c_std"
    compile "$cc" ${std_flag:+"$std_flag"} "${cflags[@]}" -o "$binary" "$source" -lm
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

# Run the solution with stdin $1 and stdout $2. Returns 124 if it was stopped
# after $limit seconds, else the solution's exit code.
run_solution() {
    if [ -z "$limit" ]; then
        "${cmd[@]}" <"$1" >"$2"
        return
    fi
    local flag="$run_dir/.timed_out" pid watcher status
    rm -f "$flag"
    # Own process group, so that a timeout also kills what the solution started.
    set -m
    "${cmd[@]}" <"$1" >"$2" &
    pid=$!
    set +m
    (
        trap 'kill "$timer" 2>/dev/null; exit' TERM
        sleep "$limit" &
        timer=$!
        wait "$timer" && touch "$flag" && kill -KILL -- -"$pid"
    ) </dev/null >/dev/null 2>&1 &
    watcher=$!
    trap 'kill "$watcher" 2>/dev/null; kill -KILL -- -"$pid" 2>/dev/null; exit 130' INT TERM
    wait "$pid" 2>/dev/null
    status=$?
    trap - INT TERM
    kill "$watcher" 2>/dev/null
    wait "$watcher" 2>/dev/null
    if [ -e "$flag" ]; then
        rm -f "$flag"
        return 124
    fi
    return "$status"
}

mkdir -p "$outputs_dir"
failed=0
if [ "${#cmd[@]}" -gt 0 ]; then
    stamp="$(date +%Y-%m-%d_%H-%M-%S)"
    run_dir="$runs_dir/$stamp"
    n=2
    while [ -e "$run_dir" ]; do
        run_dir="$runs_dir/${stamp}_$n"
        n=$((n + 1))
    done
    mkdir -p "$run_dir"
    log="$run_dir/log.txt"
    {
        echo "Command: ${cmd[*]}"
        echo "Time limit: ${limit:-none}${limit:+ seconds}"
        echo "Inputs: ${tests:-all}"
    } >"$log"
    ok=0
    crashed=0
    slow=0
    for input in "$inputs_dir/sample_$in_prefix"*.txt "$inputs_dir/$in_prefix"*.txt; do
        [ -e "$input" ] || continue
        # in_01 -> 01, sample_in_01 -> sample_01
        name="$(basename "$input" .txt)"
        id="${name/"$in_prefix"/}"
        if [ -n "$tests" ] && [[ " $tests " != *" $name.txt "* ]]; then
            continue
        fi
        echo "Running on $name.txt"
        answer="$run_dir/$out_prefix$id.txt"
        run_solution "$input" "$answer"
        status=$?
        if [ "$status" -eq 0 ]; then
            cp "$answer" "$outputs_dir/"
            echo "$name.txt: ok" >>"$log"
            ok=$((ok + 1))
        elif [ "$status" -eq 124 ]; then
            echo "WARNING: stopped $name.txt after $limit seconds (--timeout), skipped it" >&2
            echo "$name.txt: stopped after $limit seconds" >>"$log"
            slow=$((slow + 1))
            failed=1
        else
            echo "WARNING: the solution failed on $name.txt, skipped it" >&2
            echo "$name.txt: failed (exit code $status)" >>"$log"
            crashed=$((crashed + 1))
            failed=1
        fi
    done
    echo "This run: $ok ok, $crashed failed, $slow stopped by --timeout." \
        "Saved in runs/$(basename "$run_dir")/"
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
