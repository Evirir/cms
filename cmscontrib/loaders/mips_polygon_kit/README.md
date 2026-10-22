# Output-only task kit

For this task you don't submit code. You submit the output files for the given
inputs, and each one is scored on its own.

## What's in this folder

| Path | What it is |
|---|---|
| `inputs/` | The samples `sample_in_01.txt`, ..., then the inputs `in_01.txt`, `in_02.txt`, ... |
| `code/` | Templates: `solution.cpp`, `solution.c`, `solution.py`, `Solution.java`, `solution.cs`, `solution.rs`, `solution.php`, `solution.hs`, `solution.pas` |
| `run.sh` | Script for Linux and macOS |
| `run.bat` | Script for Windows |

## Steps

1. Write your solution in the template for your language in `code/`. It
   reads **one** input from standard input and prints the answer to
   standard output.
2. Open a terminal in this folder (see
   [Opening a terminal in this folder](#opening-a-terminal-in-this-folder)),
   type the command for your language and press Enter. It runs your
   solution on every input:

   | Language | Template | Linux / macOS | Windows | Needs |
   |---|---|---|---|---|
   | C++ | `solution.cpp` | `./run.sh cpp` | `run.bat cpp` | `g++`, `clang++` or MSVC `cl` |
   | C | `solution.c` | `./run.sh c` | `run.bat c` | `gcc`, `clang` or MSVC `cl` |
   | Python | `solution.py` | `./run.sh py` | `run.bat py` | `python3`/`python` (Windows: `py`/`python`) |
   | Java | `Solution.java` | `./run.sh java` | `run.bat java` | JDK (`javac`, `java`) |
   | C# | `solution.cs` | `./run.sh cs` | `run.bat cs` | Mono (`mcs`, `mono`); Windows: `csc` or Mono |
   | Rust | `solution.rs` | `./run.sh rs` | `run.bat rs` | `rustc` |
   | PHP | `solution.php` | `./run.sh php` | `run.bat php` | `php` |
   | Haskell | `solution.hs` | `./run.sh hs` | `run.bat hs` | `ghc` |
   | Pascal | `solution.pas` | `./run.sh pas` | `run.bat pas` | `fpc` |
   | Anything else | | `./run.sh COMMAND` | `run.bat COMMAND` | |

   For example, `./run.sh node code/solution.js` or
   `run.bat path\to\solution.exe`. The command is run once per input, with
   the input on standard input.
3. The script writes `outputs/out_sample_01.txt`, ..., `outputs/out_01.txt`,
   `outputs/out_02.txt`, ... and
   zips them into `output.zip`.
4. In CMS, open the task, choose `output.zip` in the submission form and submit.

## Opening a terminal in this folder

A terminal is a window where you type commands. First extract (unzip) the
kit: the scripts don't work from inside the zip. On Windows, right-click the
zip, choose **Extract All...**, then open the extracted folder, the one that
has `run.bat` and `README.md`. Then:

- **Windows:** in File Explorer, click the address bar at the top of the
  folder window, type `cmd` and press Enter. A Command Prompt opens in this
  folder; type e.g. `run.bat cpp` and press Enter.
  - If you used right-click > **Open in Terminal** instead, you are in
    PowerShell: type `.\run.bat cpp` instead of `run.bat cpp`.
- **macOS:** open **Terminal** (Applications > Utilities), type `cd ` (with a
  space after it), drag this folder from Finder onto the Terminal window and
  press Enter. Then type e.g. `./run.sh cpp`.
- **Linux:** right-click inside the folder in your file manager and choose
  **Open in Terminal**, then type e.g. `./run.sh cpp`.
- **VS Code:** choose File > Open Folder... and open this folder, then
  Terminal > New Terminal. The terminal opens in this folder. On Windows it
  is PowerShell, so type `.\run.bat cpp`.
- **Code::Blocks, Dev-C++ and other IDEs without a terminal:** keep editing
  `code/solution.cpp` (or your language's template) in the IDE, save it, and
  use the Windows/macOS/Linux steps above to run the script.

If `./run.sh` says "Permission denied", type `bash run.sh cpp` instead.
If a command says the compiler or language isn't found, see
[No compiler found?](#no-compiler-found).

## Tips

- Only run some inputs: `TESTS="sample_01 03" ./run.sh cpp` on Linux/macOS, or
  `set TESTS=sample_01 03` and then `run.bat cpp` on Windows
  (PowerShell: `$env:TESTS="sample_01 03"` and then `.\run.bat cpp`). The other files in
  `outputs/` are kept, so you can use a different program for each input.
- Made some outputs by hand? Put them in `outputs/` as `out_XX.txt` and run
  `./run.sh zip` or `run.bat zip` to only zip them.
- `output.zip` must contain only `out_XX.txt` files, otherwise CMS rejects
  the whole submission. You can also submit some of the files on their own.
- If the solution crashes on an input, the script warns you and keeps going,
  so the other outputs still get submitted.
- The C++ option uses the first compiler it finds: `g++`, then `clang++`,
  then (Windows only) MSVC's `cl`. Set `CXX` to pick one, e.g. `CXX=clang++`.
  The C option does the same with `gcc`, `clang`, `cl` and `CC`. MSVC is
  only found when you run the script from a "Developer Command Prompt for
  VS".
- C++ and C get the same flags as CMS, e.g. C++20 with
  `-DEVAL -std=gnu++20 -O2 -pipe -static -s` (not static on macOS); MSVC
  gets `/DEVAL /std:c++20 /O2 /EHsc` (`/std:c11` for C).
- On Windows without Mono, the C# option uses the `csc` that comes with the
  .NET Framework, which only knows C# 5.

## No compiler found?

Use whichever of these suits you:

1. **Point the script at your compiler.** If it isn't on your `PATH`, for
   example the MinGW that comes with Code::Blocks or Dev-C++, or `cl.exe`:
   `set CXX=C:\path\to\g++.exe` and then `run.bat cpp` on Windows, or
   `CXX=/path/to/g++ ./run.sh cpp` on Linux/macOS (`CC` for C). For other
   languages, add the compiler's folder to your `PATH`.
2. **Compile in your IDE**, then give the script the program it built:
   `run.bat path\to\solution.exe` or `./run.sh path/to/solution`.
3. **No terminal at all:** run your program on each input yourself, for
   example in your IDE, and save each answer as `outputs/out_XX.txt` with
   the same number as `inputs/in_XX.txt` (`out_sample_XX.txt` for
   `sample_in_XX.txt`). Then run `run.bat zip` or
   `./run.sh zip`, or zip the `out_XX.txt` files yourself. The files must
   be at the top of the zip, not inside a folder.
