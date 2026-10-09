@echo off
rem Run a solution on every input in inputs\ and zip the outputs for CMS.
rem
rem   run.bat cpp            compile and run code\solution.cpp
rem   run.bat py             run code\solution.py
rem   run.bat COMMAND...     run any command, e.g. run.bat java Solution
rem   run.bat zip            only zip the files already in outputs\
rem
rem Set TESTS to run only some inputs, e.g. set TESTS=00 03 then run.bat cpp
rem Outputs of the other inputs in outputs\ are kept.
setlocal

set "DIR=%~dp0"
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
echo   run.bat py             run code\solution.py
echo   run.bat COMMAND...     run any command, e.g. run.bat java Solution
echo   run.bat zip            only zip the files already in outputs\
echo Set TESTS to run only some inputs, e.g. set TESTS=00 03 then run.bat cpp
exit /b 1

:cpp
echo Compiling code\solution.cpp
g++ -std=c++17 -O2 -o "%DIR%code\solution.exe" "%DIR%code\solution.cpp"
if errorlevel 1 exit /b 1
set CMD="%DIR%code\solution.exe"
goto run

:py
where py >nul 2>nul
if errorlevel 1 (set CMD=python "%DIR%code\solution.py") else set CMD=py "%DIR%code\solution.py"
goto run

:run
if not exist "%DIR%outputs" mkdir "%DIR%outputs"
set FAILED=0
if not defined CMD goto zip
pushd "%DIR%inputs"
for %%F in (input_*.txt) do call :one "%%~fF" "%%~nF"
popd

:zip
if exist "%DIR%output.zip" del "%DIR%output.zip"
if not exist "%DIR%outputs\output_*.txt" (
    echo No files in outputs\ to zip. 1>&2
    exit /b 1
)
powershell -NoProfile -Command "Compress-Archive -Path '%DIR%outputs\output_*.txt' -DestinationPath '%DIR%output.zip'" 2>nul
if not exist "%DIR%output.zip" (
    pushd "%DIR%outputs"
    tar -a -c -f "%DIR%output.zip" output_*.txt 2>nul
    popd
)
if not exist "%DIR%output.zip" (
    echo Could not create output.zip. Zip outputs\output_*.txt yourself. 1>&2
    exit /b 1
)
echo Created output.zip. Submit it in CMS.
exit /b %FAILED%

rem Run the solution on one input. %1 is its full path, %2 is e.g. input_00.
:one
set "ID=%~2"
set "ID=%ID:~6%"
if not defined TESTS goto one_run
set WANTED=0
for %%T in (%TESTS%) do if "%%T"=="%ID%" set WANTED=1
if "%WANTED%"=="0" goto :eof
:one_run
echo Running on input_%ID%.txt
%CMD% < "%~1" > "%DIR%outputs\output_%ID%.txt"
if errorlevel 1 (
    echo WARNING: the solution failed on input_%ID%.txt 1>&2
    set FAILED=1
)
goto :eof
