# Output-only task kit

In this task you don't submit code. You get some input files, and you submit
an answer file (output) for each one. Each answer is scored on its own.

You can make the answers any way you like: with a program in any language,
by hand, or both. This kit is only there to make it easier.

## What's in this folder

| Path      | What it is                                                              |
|-----------|-------------------------------------------------------------------------|
| `inputs/` | The input files: samples `sample_in_01.txt`, ..., then `in_01.txt`, ... |
| `code/`   | Templates for your program, one per language. They are optional.        |
| `run.bat` | Windows script: runs your program on every input, makes `output.zip`    |
| `run.sh`  | The same script for macOS and Linux                                     |

## Quick start

1. **Extract (unzip) this kit.** The scripts don't work from inside the zip.
   On Windows, right-click the zip and choose **Extract All...**.
2. **Write your program.** It reads **one** input (from standard input, like
   reading what the user types) and prints the answer. The script runs it
   once for each input file.
   - You can start from the template for your language in `code/`, e.g.
     `code/solution.cpp`, or use your own file. Templates are optional.
3. **Open a terminal in this folder.** See "Opening a terminal in this
   folder" below.
4. **Type the command for your language and press Enter:**

   | Language | Template | Windows | macOS / Linux |
   |---|---|---|---|
   | C++ | `solution.cpp` | `run.bat cpp` | `./run.sh cpp` |
   | C | `solution.c` | `run.bat c` | `./run.sh c` |
   | Python | `solution.py` | `run.bat py` | `./run.sh py` |
   | Java | `Solution.java` | `run.bat java` | `./run.sh java` |
   | C# | `solution.cs` | `run.bat cs` | `./run.sh cs` |
   | Rust | `solution.rs` | `run.bat rs` | `./run.sh rs` |
   | PHP | `solution.php` | `run.bat php` | `./run.sh php` |
   | Haskell | `solution.hs` | `run.bat hs` | `./run.sh hs` |
   | Pascal | `solution.pas` | `run.bat pas` | `./run.sh pas` |

   These commands use the template file in `code/`. Using your own file or
   another language? Give the script the command that runs your program:
   - a program you compiled yourself, e.g. in your IDE:
     `run.bat C:\path\to\solution.exe` or `./run.sh path/to/solution`
   - a script: `run.bat python mycode.py` or `./run.sh node mycode.js`
5. **The script makes `output.zip`.** It also saves each answer in `outputs/`:
   `out_01.txt` is the answer for `in_01.txt`, `out_sample_01.txt` for
   `sample_in_01.txt`, and so on.
6. **Submit `output.zip` in CMS:** open the task, choose `output.zip` in the
   submission form and submit.

## Opening a terminal in this folder

A terminal is a window where you type commands. Open it in the extracted
folder, the one that has `run.bat` and this `README.md`.

- **Windows:** open the folder in File Explorer, click the address bar at the
  top of the window, type `cmd` and press Enter. A Command Prompt opens in
  this folder. Type e.g. `run.bat cpp` and press Enter.
  - If you opened it with right-click > **Open in Terminal**, it is
    PowerShell: type `.\run.bat cpp` instead of `run.bat cpp`.
- **macOS:** open **Terminal** (Applications > Utilities), type `cd ` (with a
  space after it), drag this folder from Finder onto the Terminal window and
  press Enter. Then type e.g. `./run.sh cpp`.
- **Linux:** right-click inside the folder in your file manager and choose
  **Open in Terminal**, then type e.g. `./run.sh cpp`.
- **VS Code:** choose File > Open Folder... and open this folder, then
  Terminal > New Terminal. On Windows this is PowerShell, so type
  `.\run.bat cpp`.
- **Code::Blocks, Dev-C++ and other IDEs without a terminal:** keep writing
  and saving your code in the IDE, and open a terminal with the Windows,
  macOS or Linux steps above to run the script.

## Not using the scripts

You can also make the answer files yourself, e.g. by running your program
in your IDE and copying its output, or by working an answer out by hand.

1. Save each answer as a text file named after its input: `out_01.txt` for
   `in_01.txt`, `out_sample_01.txt` for `sample_in_01.txt`.
2. Submit the files in CMS one by one, or zip them together. In the zip,
   the files must not be inside a folder, and it must contain only
   `out_...txt` files, otherwise CMS rejects the whole zip.
   - The scripts can zip them for you: put them in `outputs/`, then run
     `run.bat zip` or `./run.sh zip`.

## Something went wrong?

- **"No ... compiler found" or "No Python found":** the script can't find
  the tool for your language. You can:
  - install it (the message says where from);
  - compile your program in your IDE, then give the script the program it
    built: `run.bat C:\path\to\solution.exe` or `./run.sh path/to/solution`;
  - for C/C++, tell the script where your compiler is, e.g. the MinGW that
    comes with Code::Blocks or Dev-C++: `set CXX=C:\path\to\g++.exe`, then
    `run.bat cpp` (use `CC` instead of `CXX` for C). On macOS/Linux:
    `CXX=/path/to/g++ ./run.sh cpp`;
  - make the answers without the scripts, see "Not using the scripts"
    above.
- **"Permission denied" from `./run.sh`:** type `bash run.sh cpp` instead.
- **"WARNING: the solution failed on ...":** your program crashed or gave an
  error on that input. The script still runs the other inputs and makes
  `output.zip`, so you can submit the answers that worked.
- **Changed only some answers?** Files in `outputs/` you didn't rerun are
  kept and go into `output.zip` too.

## More details

- **Running only some inputs:** set `TESTS` to the input names without `in_`
  and `.txt`, e.g.
  for `sample_in_01.txt` and `in_03.txt`:
  - Command Prompt: `set TESTS=sample_01 03`, then `run.bat cpp`
  - PowerShell: `$env:TESTS="sample_01 03"`, then `.\run.bat cpp`
  - macOS/Linux: `TESTS="sample_01 03" ./run.sh cpp`

  This way you can use a different program for some inputs.
- **What each language needs installed:** C++: `g++`, `clang++` or (Windows)
  MSVC `cl`. C: `gcc`, `clang` or MSVC `cl`. Python: `python3`/`python`
  (Windows: `py`/`python`). Java: a JDK (`javac`, `java`). C#: Mono (`mcs`,
  `mono`); on Windows also `csc`. Rust: `rustc`. PHP: `php`. Haskell: `ghc`.
  Pascal: `fpc`. Other than `CXX`/`CC` for C/C++, the tool must be on your
  `PATH`.
- **Which C/C++ compiler is used:** the first one found of `g++`, `clang++`,
  then (Windows only) MSVC's `cl` for C++, and `gcc`, `clang`, `cl` for C.
  Set `CXX` (C++) or `CC` (C) to choose one. MSVC is only found when you run
  the script from a "Developer Command Prompt for VS".
- **Compiler flags:** C++ and C get the same flags as CMS, e.g.
  `-DEVAL -std=gnu++20 -O2 -pipe -static -s` for C++ (not static on macOS).
  MSVC gets `/DEVAL /std:c++20 /O2 /EHsc` (`/std:c11` for C).
- **C# on Windows without Mono:** the script uses the `csc` that comes with
  Windows (.NET Framework), which only knows C# 5.
