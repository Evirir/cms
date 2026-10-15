# Output-only task kit

For this task you don't submit code. You submit the output files for the given
inputs, and each one is scored on its own.

## What's in this folder

| Path | What it is |
|---|---|
| `inputs/` | The samples `sample_input_01.txt`, ..., then the inputs `input_01.txt`, `input_02.txt`, ... |
| `code/solution.cpp` | C++ template |
| `code/solution.py` | Python template |
| `run.sh` | Script for Linux and macOS |
| `run.bat` | Script for Windows |

## Steps

1. Write your solution in `code/solution.cpp` or `code/solution.py`. It reads
   **one** input from standard input and prints the answer to standard output.
2. Open a terminal in this folder and run your solution on every input:

   | Language | Linux / macOS | Windows |
   |---|---|---|
   | C++ | `./run.sh cpp` | `run.bat cpp` |
   | Python | `./run.sh py` | `run.bat py` |
   | Anything else | `./run.sh COMMAND` | `run.bat COMMAND` |

   For example, `./run.sh java Solution` or `run.bat node code\solution.js`.
   The command is run once per input, with the input on standard input.
3. The script writes `outputs/output_sample_01.txt`, ..., `outputs/output_01.txt`,
   `outputs/output_02.txt`, ... and
   zips them into `output.zip`.
4. In CMS, open the task, choose `output.zip` in the submission form and submit.

## Tips

- Only run some inputs: `TESTS="sample_01 03" ./run.sh cpp` on Linux/macOS, or
  `set TESTS=sample_01 03` and then `run.bat cpp` on Windows. The other files in
  `outputs/` are kept, so you can use a different program for each input.
- Made some outputs by hand? Put them in `outputs/` as `output_XX.txt` and run
  `./run.sh zip` or `run.bat zip` to only zip them.
- `output.zip` must contain only `output_XX.txt` files, otherwise CMS rejects
  the whole submission. You can also submit some of the files on their own.
- If the solution crashes on an input, the script warns you and keeps going,
  so the other outputs still get submitted.
- The C++ option uses the first compiler it finds: `g++`, then `clang++`,
  then (Windows only) MSVC's `cl`. Set `CXX` to pick one, e.g. `CXX=clang++`.
  `g++` and `clang++` get the same flags as CMS's C++20
  (`-DEVAL -std=gnu++20 -O2 -pipe -static -s`; not static on macOS), and
  MSVC gets `/DEVAL /std:c++20 /O2 /EHsc`. MSVC is only found when you run
  the script from a "Developer Command Prompt for VS".
- The Python option needs `python3`/`python` (Linux/macOS) or `py`/`python`
  (Windows).

## No compiler found?

Use whichever of these suits you:

1. **Point the script at your compiler.** If it isn't on your `PATH`, for
   example the MinGW that comes with Code::Blocks or Dev-C++, or `cl.exe`:
   `set CXX=C:\path\to\g++.exe` and then `run.bat cpp` on Windows, or
   `CXX=/path/to/g++ ./run.sh cpp` on Linux/macOS.
2. **Compile in your IDE**, then give the script the program it built:
   `run.bat path\to\solution.exe` or `./run.sh path/to/solution`.
3. **No terminal at all:** run your program on each input yourself, for
   example in your IDE, and save each answer as `outputs/output_XX.txt` with
   the same number as `inputs/input_XX.txt` (`output_sample_XX.txt` for
   `sample_input_XX.txt`). Then run `run.bat zip` or
   `./run.sh zip`, or zip the `output_XX.txt` files yourself. The files must
   be at the top of the zip, not inside a folder.
