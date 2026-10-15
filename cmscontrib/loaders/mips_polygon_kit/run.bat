@echo off
rem Run a solution on every input in inputs\ and zip the outputs for CMS.
rem
rem   run.bat cpp            compile and run code\solution.cpp
rem                          (g++, clang++ or MSVC cl; set CXX to choose one)
rem   run.bat py             run code\solution.py
rem   run.bat COMMAND...     run any command, e.g. run.bat java Solution
rem   run.bat zip            only zip the files already in outputs\
rem
rem Set TESTS to run only some inputs, e.g. set TESTS=00 03 then run.bat cpp
rem Outputs of the other inputs in outputs\ are kept. No compiler? See README.md.
setlocal

set "DIR=%~dp0"
set "INPUTS=%DIR%inputs"
set "OUTPUTS=%DIR%outputs"
set "ZIP=%DIR%output.zip"
set "IN_PREFIX=input_"
set "OUT_PREFIX=output_"
set "CPP_SOURCE=%DIR%code\solution.cpp"
set "CPP_BINARY=%DIR%code\solution.exe"
set "CPP_OBJECT=%DIR%code\solution.obj"
set "PY_SOURCE=%DIR%code\solution.py"
rem Same flags as the CMS "C++20 / g++" language.
set "CXXFLAGS=-DEVAL -std=gnu++20 -O2 -pipe -static -s"
rem The closest MSVC (cl, clang-cl) equivalent.
set "MSVC_FLAGS=/nologo /DEVAL /std:c++20 /O2 /EHsc"
set "MODE=%~1"
set "CMD="

if "%MODE%"=="" goto usage
if /i "%MODE%"=="cpp" goto cpp
if /i "%MODE%"=="py" goto py
if /i "%MODE%"=="zip" goto run
set CMD=%*
goto run

:usage
echo Usage:
echo   run.bat cpp            compile and run code\solution.cpp
echo                          (g++, clang++ or MSVC cl; set CXX to choose one)
echo   run.bat py             run code\solution.py
echo   run.bat COMMAND...     run any command, e.g. run.bat java Solution
echo   run.bat zip            only zip the files already in outputs\
echo Set TESTS to run only some inputs, e.g. set TESTS=00 03 then run.bat cpp
echo No compiler? See README.md.
exit /b 1

:cpp
if not defined CXX call :find_cxx
if not defined CXX goto no_cxx
for %%N in ("%CXX%") do set "CXX_NAME=%%~nN"
echo Compiling code\solution.cpp with %CXX%
if /i "%CXX_NAME%"=="cl" goto cpp_msvc
if /i "%CXX_NAME%"=="clang-cl" goto cpp_msvc
"%CXX%" %CXXFLAGS% -o "%CPP_BINARY%" "%CPP_SOURCE%"
goto cpp_done
:cpp_msvc
"%CXX%" %MSVC_FLAGS% /Fe"%CPP_BINARY%" /Fo"%CPP_OBJECT%" "%CPP_SOURCE%"
:cpp_done
if errorlevel 9009 goto no_cxx
if errorlevel 1 exit /b 1
set CMD="%CPP_BINARY%"
goto run

rem Set CXX to the first C++ compiler found: g++, clang++, then MSVC's cl.
:find_cxx
g++ --version >nul 2>nul
if not errorlevel 1 (
    set "CXX=g++"
    goto :eof
)
clang++ --version >nul 2>nul
if not errorlevel 1 (
    set "CXX=clang++"
    goto :eof
)
where cl >nul 2>nul
if not errorlevel 1 set "CXX=cl"
goto :eof

:no_cxx
echo No C++ compiler found. Compile code\solution.cpp yourself, e.g. in 1>&2
echo your IDE, then run: run.bat path\to\your\program.exe 1>&2
echo Or set CXX to your compiler, e.g. set CXX=C:\path\to\g++.exe then run.bat cpp 1>&2
echo For MSVC, run this from a "Developer Command Prompt for VS". 1>&2
exit /b 1

:py
py --version >nul 2>nul
if not errorlevel 1 (
    set CMD=py "%PY_SOURCE%"
    goto run
)
python --version >nul 2>nul
if not errorlevel 1 (
    set CMD=python "%PY_SOURCE%"
    goto run
)
echo Python not found. Install Python 3 from https://www.python.org 1>&2
exit /b 1

:run
if not exist "%OUTPUTS%" mkdir "%OUTPUTS%"
set FAILED=0
if not defined CMD goto zip
pushd "%INPUTS%"
for %%F in (%IN_PREFIX%*.txt) do call :one "%%~fF" "%%~nF"
popd

:zip
if exist "%ZIP%" del "%ZIP%"
if not exist "%OUTPUTS%\%OUT_PREFIX%*.txt" (
    echo No files in outputs\ to zip. 1>&2
    exit /b 1
)
powershell -NoProfile -Command "Compress-Archive -Path '%OUTPUTS%\%OUT_PREFIX%*.txt' -DestinationPath '%ZIP%'" 2>nul
if not exist "%ZIP%" (
    pushd "%OUTPUTS%"
    tar -a -c -f "%ZIP%" %OUT_PREFIX%*.txt 2>nul
    popd
)
if not exist "%ZIP%" (
    echo Could not create output.zip. Zip outputs\%OUT_PREFIX%*.txt yourself. 1>&2
    exit /b 1
)
echo Created output.zip. Submit it in CMS.
exit /b %FAILED%

rem Run the solution on one input. %1 is its full path, %2 its name without .txt.
:one
set "ID=%~2"
call set "ID=%%ID:%IN_PREFIX%=%%"
if not defined TESTS goto one_run
set WANTED=0
for %%T in (%TESTS%) do if "%%T"=="%ID%" set WANTED=1
if "%WANTED%"=="0" goto :eof
:one_run
echo Running on %~2.txt
%CMD% < "%~1" > "%OUTPUTS%\%OUT_PREFIX%%ID%.txt"
if errorlevel 1 (
    echo WARNING: the solution failed on %~2.txt 1>&2
    set FAILED=1
)
goto :eof
