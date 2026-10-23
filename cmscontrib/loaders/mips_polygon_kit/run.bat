@echo off
rem Run a solution on every input in inputs\ and zip the outputs for CMS.
rem
rem   run.bat LANGUAGE       compile and run code\solution.* (Solution.java), where
rem                          LANGUAGE is cpp, c, py, java, cs, rs, php, hs or pas
rem   run.bat COMMAND...     run any command, e.g. run.bat node code\solution.js
rem   run.bat zip            only zip the files already in outputs\
rem
rem Options, before LANGUAGE or COMMAND:
rem   --tests in_01.txt sample_in_02.txt ...   run only on these inputs
rem   --timeout 10                             stop and skip an input after 10 s
rem   e.g. run.bat --tests in_01.txt in_03.txt --timeout 10 cpp
rem
rem Each run saves its answers and log.txt in runs\<date>_<time>\. Answers that
rem finished without crashing or timing out are copied to outputs\, which keeps
rem the latest good answer of every input and is zipped into output.zip.
rem Set CXX (cpp) or CC (c) to choose a compiler; cpp and c also find MSVC's cl.
rem No compiler? See README.md.
setlocal

set "DIR=%~dp0"
set "INPUTS=%DIR%inputs"
set "OUTPUTS=%DIR%outputs"
set "RUNS=%DIR%runs"
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
set "CMD="
set "TESTS="
set "LIMIT="

:options
if "%~1"=="" goto options_done
if "%~1"=="--tests" goto opt_tests
if "%~1"=="--timeout" goto opt_timeout
if /i "%~1"=="--help" goto usage
set "ARG=%~1"
if "%ARG:~0,1%"=="-" goto opt_unknown
goto options_done
:opt_tests
shift
set "GOT="
:opt_tests_next
if "%~1"=="" goto opt_tests_end
call :input_file "%~1"
if "%RESULT%"=="2" goto opt_tests_end
if "%RESULT%"=="1" goto opt_tests_missing
set "TESTS=%TESTS% %FILE%.txt"
set GOT=1
shift
goto opt_tests_next
:opt_tests_end
if not defined GOT goto opt_tests_empty
goto options
:opt_timeout
set "LIMIT=%~2"
if not defined LIMIT goto limit_bad
shift
shift
goto options

:options_done
set "KIT_LIMIT=%LIMIT%"
set "LIMIT="
if not defined KIT_LIMIT goto limit_ok
where powershell >nul 2>nul
if errorlevel 1 goto limit_needs_powershell
rem Exit code 0: a time limit, 2: no time limit (0 seconds), 1: not a number.
powershell -NoProfile -Command "$t=0.0; if(-not [double]::TryParse($env:KIT_LIMIT,[Globalization.NumberStyles]::Float,[Globalization.CultureInfo]::InvariantCulture,[ref]$t) -or $t -lt 0){exit 1}; if($t -eq 0){exit 2}; exit 0"
if errorlevel 2 goto limit_ok
if errorlevel 1 goto limit_bad
set "LIMIT=%KIT_LIMIT%"
:limit_ok
set "MODE=%~1"
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
rem Any other command: %* would still have the options, so rebuild it.
:command
if "%~1"=="" goto command_done
set CMD=%CMD% %1
shift
goto command
:command_done
set "CMD=%CMD:~1%"
goto run

:usage
echo Usage:
echo   run.bat LANGUAGE       compile and run code\solution.* (Solution.java), where
echo                          LANGUAGE is cpp, c, py, java, cs, rs, php, hs or pas
echo   run.bat COMMAND...     run any command, e.g. run.bat node code\solution.js
echo   run.bat zip            only zip the files already in outputs\
echo Options, before LANGUAGE or COMMAND:
echo   --tests in_01.txt sample_in_02.txt ...   run only on these inputs
echo   --timeout 10                             stop and skip an input after 10 s
echo   e.g. run.bat --tests in_01.txt in_03.txt --timeout 10 cpp
echo Each run saves its answers and log.txt in runs\^<date^>_^<time^>\. Answers that
echo finished without crashing or timing out are copied to outputs\, which keeps
echo the latest good answer of every input and is zipped into output.zip.
echo Set CXX (cpp) or CC (c) to choose a compiler; cpp and c also find MSVC's cl.
echo No compiler? See README.md.
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
set "STAMP="
for /f "delims=" %%T in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HH-mm-ss" 2^>nul') do set "STAMP=%%T"
if not defined STAMP set "STAMP=run_%RANDOM%"
set "RUN=%RUNS%\%STAMP%"
set N=2
:run_dir
if not exist "%RUN%" goto run_dir_ok
set "RUN=%RUNS%\%STAMP%_%N%"
set /a N+=1
goto run_dir
:run_dir_ok
mkdir "%RUN%"
for %%R in ("%RUN%") do set "RUN_NAME=%%~nxR"
set "LOG=%RUN%\log.txt"
set "FLAG=%RUN%\timed_out.flag"
set "KIT_FLAG=%FLAG%"
set "KIT_LIMIT=%LIMIT%"
>"%LOG%" echo Command: %CMD%
if defined LIMIT >>"%LOG%" echo Time limit: %LIMIT% seconds
if not defined LIMIT >>"%LOG%" echo Time limit: none
if defined TESTS >>"%LOG%" echo Inputs:%TESTS%
if not defined TESTS >>"%LOG%" echo Inputs: all
set OK=0
set CRASHED=0
set SLOW=0
for /f "delims=" %%F in ('dir /b /on "%INPUTS%\sample_%IN_PREFIX%*.txt" 2^>nul') do call :one "%INPUTS%\%%F" "%%~nF"
for /f "delims=" %%F in ('dir /b /on "%INPUTS%\%IN_PREFIX%*.txt" 2^>nul') do call :one "%INPUTS%\%%F" "%%~nF"
echo This run: %OK% ok, %CRASHED% failed, %SLOW% stopped by --timeout. Saved in runs\%RUN_NAME%\

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
for %%T in (%TESTS%) do if /i "%%T"=="%~2.txt" set WANTED=1
if "%WANTED%"=="0" goto :eof
:one_run
echo Running on %~2.txt
set "ANSWER=%RUN%\%OUT_PREFIX%%ID%.txt"
if exist "%FLAG%" del "%FLAG%"
if defined LIMIT goto one_limit
%CMD% < "%~1" > "%ANSWER%"
set "STATUS=%ERRORLEVEL%"
goto one_done
rem Run it through cmd from PowerShell, and kill it after LIMIT seconds.
:one_limit
set "KIT_CMD=%CMD%"
set "KIT_IN=%~1"
set "KIT_OUT=%ANSWER%"
powershell -NoProfile -Command "$q=[char]34; $a='/d /s /c '+$q+$env:KIT_CMD+' < '+$q+$env:KIT_IN+$q+' > '+$q+$env:KIT_OUT+$q+$q; $i=New-Object Diagnostics.ProcessStartInfo($env:ComSpec,$a); $i.UseShellExecute=$false; $p=[Diagnostics.Process]::Start($i); $ms=[int](1000*[double]::Parse($env:KIT_LIMIT,[Globalization.CultureInfo]::InvariantCulture)); if($p.WaitForExit($ms)){exit $p.ExitCode}; taskkill /T /F /PID $p.Id 2>&1 | Out-Null; New-Item -ItemType File -Force -Path $env:KIT_FLAG | Out-Null; exit 1"
set "STATUS=%ERRORLEVEL%"
:one_done
if exist "%FLAG%" goto one_slow
if not "%STATUS%"=="0" goto one_failed
copy /y "%ANSWER%" "%OUTPUTS%\" >nul
>>"%LOG%" echo %~2.txt: ok
set /a OK+=1
goto :eof
:one_slow
del "%FLAG%"
echo WARNING: stopped %~2.txt after %LIMIT% seconds (--timeout), skipped it 1>&2
>>"%LOG%" echo %~2.txt: stopped after %LIMIT% seconds
set /a SLOW+=1
set FAILED=1
goto :eof
:one_failed
echo WARNING: the solution failed on %~2.txt, skipped it 1>&2
>>"%LOG%" echo %~2.txt: failed (exit code %STATUS%)
set /a CRASHED+=1
set FAILED=1
goto :eof

rem Set FILE to the name of input %1 without .txt, e.g. in_01 for in_01.txt,
rem inputs\in_01.txt, in_01 or 01, and sample_in_01 for sample_01, and RESULT
rem to 0. RESULT is 1 if there is no such input, 2 if %1 doesn't look like one.
:input_file
set "RESULT=2"
set "ARG=%~1"
set "NAME=%~n1"
set "LOOKS="
if /i "%~x1"==".txt" set LOOKS=1
if not "%~x1"=="" if not defined LOOKS goto :eof
if /i not "%ARG:inputs\=%"=="%ARG%" set LOOKS=1
if /i not "%ARG:inputs/=%"=="%ARG%" set LOOKS=1
if /i "%NAME:~0,7%"=="sample_" set LOOKS=1
if /i "%NAME:~0,3%"=="%IN_PREFIX%" set LOOKS=1
set DIGITS=1
for /f "delims=0123456789" %%A in ("%NAME%") do set DIGITS=0
if "%DIGITS%"=="1" set LOOKS=1
set "FILE=%NAME%"
if /i "%NAME:~0,7%"=="sample_" if /i not "%NAME:~0,10%"=="sample_%IN_PREFIX%" set "FILE=sample_%IN_PREFIX%%NAME:~7%"
if /i not "%NAME:~0,7%"=="sample_" if /i not "%NAME:~0,3%"=="%IN_PREFIX%" set "FILE=%IN_PREFIX%%NAME%"
if not exist "%INPUTS%\%FILE%.txt" goto input_missing
set "RESULT=0"
goto :eof
:input_missing
if defined LOOKS set "RESULT=1"
goto :eof

:opt_tests_missing
echo No input named %~1 in inputs\ 1>&2
exit /b 1

:opt_tests_empty
echo --tests needs input names, e.g. --tests in_01.txt in_03.txt 1>&2
exit /b 1

:opt_unknown
echo Unknown option %~1. The options are --tests and --timeout. 1>&2
exit /b 1

:limit_bad
echo --timeout needs a number of seconds, e.g. --timeout 10 1>&2
exit /b 1

:limit_needs_powershell
echo --timeout needs PowerShell, which comes with Windows 10 and 11. 1>&2
exit /b 1
