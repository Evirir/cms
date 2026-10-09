# Output-only task kit

For this task you don't submit code. You submit the output files for the given
inputs, and each one is scored on its own.

## What's in this folder

| Path | What it is |
|---|---|
| `inputs/` | The inputs, `input_00.txt`, `input_01.txt`, ... |
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
3. The script writes `outputs/output_00.txt`, `outputs/output_01.txt`, ... and
   zips them into `output.zip`.
4. In CMS, open the task, choose `output.zip` in the submission form and submit.

## Tips

- Only run some inputs: `TESTS="00 03" ./run.sh cpp` on Linux/macOS, or
  `set TESTS=00 03` and then `run.bat cpp` on Windows. The other files in
  `outputs/` are kept, so you can use a different program for each input.
- Made some outputs by hand? Put them in `outputs/` as `output_XX.txt` and run
  `./run.sh zip` or `run.bat zip` to only zip them.
- `output.zip` must contain only `output_XX.txt` files, otherwise CMS rejects
  the whole submission. You can also submit some of the files on their own.
- If the solution crashes on an input, the script warns you and keeps going,
  so the other outputs still get submitted.
- The C++ option needs `g++` on your `PATH`, and the Python option needs
  `python3` (Linux/macOS) or `py`/`python` (Windows).
