@echo off
rem Run a solution on every input in inputs\ and zip the outputs for CMS.
rem
rem   run.bat LANGUAGE       compile and run code\solution.* (Solution.java), where
rem                          LANGUAGE is cpp, c, py, java, cs, rs, php, hs or pas
rem   run.bat COMMAND...     run any command, e.g. run.bat node code\solution.js
rem   run.bat zip            only zip the files already in outputs\
rem
rem Set CXX (cpp) or CC (c) to choose a compiler; cpp and c also find MSVC's cl.
rem Set TESTS to run only some inputs, e.g. set TESTS=sample_01 03 then run.bat cpp
rem Outputs of the other inputs in outputs\ are kept. No compiler? See README.md.
setlocal

set "DIR=%~dp0"
set "INPUTS=%DIR%inputs"
set "OUTPUTS=%DIR%outputs"
set "ZIP=%DIR%output.zip"
set "IN_PREFIX=in_"
set "OUT_PREFIX=out_"
set "CODE=%DIR%code"
set "BINARY=%DIR%code\solution.exe"
set "OBJECT=%DIR%code\solution.obj"
rem Same flags as the CMS languages.
set "CXXFLAGS=-DEVAL -std=gnu++20 -O2 -pipe -static -s"
set "CFLAGS=-DEVAL -std=gnu11 -O2 -pipe -static -s"
rem The closest MSVC (cl, clang-cl) equivalents.
set "MSVC_CXXFLAGS=/nologo /DEVAL /std:c++20 /O2 /EHsc"
set "MSVC_CFLAGS=/nologo /DEVAL /std:c11 /O2"
set "MODE=%~1"
set "CMD="

if "%MODE%"=="" goto usage
if /i "%MODE%"=="cpp" goto lang_cpp
if /i "%MODE%"=="c" goto lang_c
if /i "%MODE%"=="py" goto lang_py
if /i "%MODE%"=="java" goto lang_java
if /i "%MODE%"=="cs" goto lang_cs
if /i "%MODE%"=="rs" goto lang_rs
if /i "%MODE%"=="php" goto lang_php
if /i "%MODE%"=="hs" goto lang_hs
if /i "%MODE%"=="pas" goto lang_pas
if /i "%MODE%"=="zip" goto run
set CMD=%*
goto run

:usage
echo Usage:
echo   run.bat LANGUAGE       compile and run code\solution.* (Solution.java), where
echo                          LANGUAGE is cpp, c, py, java, cs, rs, php, hs or pas
echo   run.bat COMMAND...     run any command, e.g. run.bat node code\solution.js
echo   run.bat zip            only zip the files already in outputs\
echo Set CXX (cpp) or CC (c) to choose a compiler; cpp and c also find MSVC's cl.
echo Set TESTS to run only some inputs, e.g. set TESTS=sample_01 03 then run.bat cpp
echo Outputs of the other inputs in outputs\ are kept. No compiler? See README.md.
exit /b 1

:lang_cpp
set "SOURCE=code\solution.cpp"
set "WHAT=C++ compiler"
set "HINT=Set CXX to yours, e.g. set CXX=C:\path\to\g++.exe then run.bat cpp"
if not defined CXX call :find_compiler CXX g++ clang++
if not defined CXX goto missing
set "COMPILER=%CXX%"
set "FLAGS=%CXXFLAGS%"
set "MSVC_FLAGS=%MSVC_CXXFLAGS%"
set "LIBS="
goto compile_c_family

:lang_c
set "SOURCE=code\solution.c"
set "WHAT=C compiler"
set "HINT=Set CC to yours, e.g. set CC=C:\path\to\gcc.exe then run.bat c"
if not defined CC call :find_compiler CC gcc clang
if not defined CC goto missing
set "COMPILER=%CC%"
set "FLAGS=%CFLAGS%"
set "MSVC_FLAGS=%MSVC_CFLAGS%"
set "LIBS=-lm"

:compile_c_family
for %%N in ("%COMPILER%") do set "COMPILER_NAME=%%~nN"
echo Compiling %SOURCE% with %COMPILER%
if /i "%COMPILER_NAME%"=="cl" goto compile_msvc
if /i "%COMPILER_NAME%"=="clang-cl" goto compile_msvc
"%COMPILER%" %FLAGS% -o "%BINARY%" "%DIR%%SOURCE%" %LIBS%
goto compiled
:compile_msvc
"%COMPILER%" %MSVC_FLAGS% /Fe"%BINARY%" /Fo"%OBJECT%" "%DIR%%SOURCE%"
goto compiled

rem Set variable %1 to the first compiler found: %2, %3, then MSVC's cl.
:find_compiler
for %%P in (%2 %3) do (
    %%P --version >nul 2>nul
    if not errorlevel 1 (
        set "%1=%%P"
        goto :eof
    )
)
where cl >nul 2>nul
if not errorlevel 1 set "%1=cl"
goto :eof

:lang_py
set "WHAT=Python"
set "HINT=Install Python 3 from https://www.python.org"
py --version >nul 2>nul
if not errorlevel 1 (
    set CMD=py "%CODE%\solution.py"
    goto run
)
python --version >nul 2>nul
if not errorlevel 1 (
    set CMD=python "%CODE%\solution.py"
    goto run
)
goto missing

:lang_java
set "SOURCE=code\Solution.java"
set "WHAT=Java compiler (javac)"
set "HINT=Install a JDK, e.g. from https://adoptium.net"
where javac >nul 2>nul
if errorlevel 1 goto missing
set CMD=java -Deval=true -Xss64M -cp "%CODE%" Solution
echo Compiling %SOURCE% with javac
javac -d "%CODE%" "%DIR%%SOURCE%"
goto compiled

:lang_cs
set "SOURCE=code\solution.cs"
set "WHAT=C# compiler (csc or mcs)"
set "HINT=Install the .NET Framework 4 or Mono from https://www.mono-project.com"
set "CSC="
for %%P in (csc mcs) do if not defined CSC (
    where %%P >nul 2>nul
    if not errorlevel 1 set "CSC=%%P"
)
set "NETFX=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if not defined CSC if exist "%NETFX%" set "CSC=%NETFX%"
set "NETFX=%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe"
if not defined CSC if exist "%NETFX%" set "CSC=%NETFX%"
if not defined CSC goto missing
echo Compiling %SOURCE% with %CSC%
rem call, because Mono's mcs is a batch file.
call "%CSC%" -out:"%BINARY%" -optimize+ "%DIR%%SOURCE%"
goto compiled

:lang_rs
set "SOURCE=code\solution.rs"
set "WHAT=Rust compiler (rustc)"
set "HINT=Install Rust from https://rustup.rs"
where rustc >nul 2>nul
if errorlevel 1 goto missing
echo Compiling %SOURCE% with rustc
rustc -O -o "%BINARY%" "%DIR%%SOURCE%"
goto compiled

:lang_php
set "WHAT=PHP"
set "HINT=Install PHP from https://www.php.net"
where php >nul 2>nul
if errorlevel 1 goto missing
set CMD=php -d memory_limit=-1 "%CODE%\solution.php"
goto run

:lang_hs
set "SOURCE=code\solution.hs"
set "WHAT=Haskell compiler (ghc)"
set "HINT=Install GHC from https://www.haskell.org/ghcup"
where ghc >nul 2>nul
if errorlevel 1 goto missing
echo Compiling %SOURCE% with ghc
ghc -O2 -o "%BINARY%" "%DIR%%SOURCE%"
goto compiled

:lang_pas
set "SOURCE=code\solution.pas"
set "WHAT=Pascal compiler (fpc)"
set "HINT=Install Free Pascal from https://www.freepascal.org"
where fpc >nul 2>nul
if errorlevel 1 goto missing
echo Compiling %SOURCE% with fpc
fpc -dEVAL -O2 -o"%BINARY%" "%DIR%%SOURCE%"
goto compiled

:compiled
if errorlevel 9009 goto missing
if errorlevel 1 exit /b 1
if not defined CMD set CMD="%BINARY%"
goto run

:missing
echo No %WHAT% found. %HINT% 1>&2
if /i "%MODE%"=="cpp" echo For MSVC, run this from a "Developer Command Prompt for VS". 1>&2
if /i "%MODE%"=="py" exit /b 1
if /i "%MODE%"=="php" exit /b 1
echo Or compile %SOURCE% yourself, e.g. in your IDE, then run: 1>&2
echo run.bat path\to\your\program.exe 1>&2
exit /b 1

:run
if not exist "%OUTPUTS%" mkdir "%OUTPUTS%"
set FAILED=0
if not defined CMD goto zip
pushd "%INPUTS%"
for %%F in (sample_%IN_PREFIX%*.txt) do call :one "%%~fF" "%%~nF"
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
rem Its ID drops the in_ prefix: in_01 -> 01, sample_in_01 -> sample_01.
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
