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
rem   --std 17                                 cpp and c: compile as C++17 (gnu++17
rem                                            if the compiler has it), or e.g.
rem                                            --std c++17, --std gnu++17, --std c99
rem   e.g. run.bat --tests in_01.txt in_03.txt --timeout 10 cpp
rem
rem Each run saves its answers and log.txt in runs\<date>_<time>\. Answers that
rem finished without crashing or timing out are copied to outputs\, which keeps
rem the latest good answer of every input and is zipped into output.zip.
rem Without --std, cpp and c use the newest standard up to the one CMS uses
rem (gnu++20, gnu11) that the compiler has.
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
rem Same flags as the CMS languages, which use C++20 and C11. -std is added
rem later.
set "CMS_CXX_STD=20"
set "CMS_C_STD=11"
set "CXXFLAGS=-DEVAL -O2 -pipe -static -s"
set "CFLAGS=-DEVAL -O2 -pipe -static -s"
rem The closest MSVC (cl, clang-cl) equivalents.
set "MSVC_CXXFLAGS=/nologo /DEVAL /O2 /EHsc"
set "MSVC_CFLAGS=/nologo /DEVAL /O2"
rem Empty files that cl compiles to check that it knows a /std.
set "STD_CHECK=%DIR%code\std_check"
set "CMD="
set "TESTS="
set "LIMIT="
set "STD="

:options
if "%~1"=="" goto options_done
if "%~1"=="--tests" goto opt_tests
if "%~1"=="--timeout" goto opt_timeout
if "%~1"=="--std" goto opt_std
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
:opt_std
set "STD=%~2"
rem It must be gnu++, c++, gnu, c or nothing, then two characters, a digit first.
set "VERSION=%STD%"
if not defined VERSION goto std_bad
if /i "%VERSION:~0,3%"=="gnu" set "VERSION=%VERSION:~3%"
if not defined VERSION goto std_bad
if /i "%VERSION:~0,1%"=="c" set "VERSION=%VERSION:~1%"
if not defined VERSION goto std_bad
if "%VERSION:~0,2%"=="++" set "VERSION=%VERSION:~2%"
if not defined VERSION goto std_bad
if "%VERSION:~1%"=="" goto std_bad
if not "%VERSION:~2%"=="" goto std_bad
for /f "delims=0123456789" %%A in ("%VERSION:~0,1%") do goto std_bad
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
if defined STD if /i not "%MODE%"=="cpp" if /i not "%MODE%"=="c" goto std_mode
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
echo   --std 17                                 cpp and c: compile as C++17 (gnu++17
echo                                            if the compiler has it), or e.g.
echo                                            --std c++17, --std gnu++17, --std c99
echo   e.g. run.bat --tests in_01.txt in_03.txt --timeout 10 cpp
echo Each run saves its answers and log.txt in runs\^<date^>_^<time^>\. Answers that
echo finished without crashing or timing out are copied to outputs\, which keeps
echo the latest good answer of every input and is zipped into output.zip.
echo Without --std, cpp and c use the newest standard up to the one CMS uses
echo (gnu++20, gnu11) that the compiler has.
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
set "STD_LANG=c++"
set "GNU_PREFIX=gnu++"
set "STD_NAME=C++"
set "CMS_STD=%CMS_CXX_STD%"
set "STD_EXAMPLE=17"
set "AUTO_VERSIONS=20 2a 17 1z 14 1y 11 0x"
set "MSVC_AUTO=c++20 c++latest c++17 c++14"
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
set "STD_LANG=c"
set "GNU_PREFIX=gnu"
set "STD_NAME=C"
set "CMS_STD=%CMS_C_STD%"
set "STD_EXAMPLE=99"
set "AUTO_VERSIONS=11 1x 99 9x"
set "MSVC_AUTO=c11"

:compile_c_family
for %%N in ("%COMPILER%") do set "COMPILER_NAME=%%~nN"
set "MSVC="
if /i "%COMPILER_NAME%"=="cl" set MSVC=1
if /i "%COMPILER_NAME%"=="clang-cl" set MSVC=1
call :pick_std
if errorlevel 1 exit /b 1
echo Compiling %SOURCE% with %COMPILER% %STD_FLAG%
if defined MSVC goto compile_msvc
"%COMPILER%" %STD_FLAG% %FLAGS% -o "%BINARY%" "%DIR%%SOURCE%" %LIBS%
goto compiled
:compile_msvc
"%COMPILER%" %STD_FLAG% %MSVC_FLAGS% /Fe"%BINARY%" /Fo"%OBJECT%" "%DIR%%SOURCE%"
goto compiled

rem Set STD_FLAG to -std=... (/std:... for MSVC): --std, or the best standard
rem up to CMS_STD that COMPILER has. GNU (gnu++17) comes before standard
rem (c++17) unless --std asks for c++ or c. MSVC only has standard ones.
:pick_std
set "STD_FLAG="
set "CHOSEN="
set "NOT_FOUND="
set "CANDIDATES="
set "KIND=gnu"
if defined MSVC set "KIND=standard"
if not defined STD goto pick_std_auto
set "VERSION=%STD%"
if /i "%VERSION:~0,3%"=="gnu" set "VERSION=%VERSION:~3%"
if /i "%VERSION%"=="%STD%" if /i "%VERSION:~0,1%"=="c" set "KIND=standard"
if /i "%VERSION%"=="%STD%" if /i "%VERSION:~0,1%"=="c" set "VERSION=%VERSION:~1%"
if "%VERSION:~0,2%"=="++" set "VERSION=%VERSION:~2%"
call :std_alias %VERSION%
for %%V in (%VERSION% %ALIAS%) do call :add_std %%V
if defined MSVC if "%STD_LANG% %VERSION%"=="c++ 20" set "CANDIDATES=%CANDIDATES% c++latest"
goto pick_std_try
:pick_std_auto
if defined MSVC set "CANDIDATES=%MSVC_AUTO%"
if not defined MSVC for %%V in (%AUTO_VERSIONS%) do call :add_std %%V
:pick_std_try
for %%S in (%CANDIDATES%) do if not defined CHOSEN call :try_std %%S
if defined MSVC del "%STD_CHECK%.*" 2>nul
if defined CHOSEN goto pick_std_found
rem No such compiler: compiling will say so.
if defined NOT_FOUND exit /b 0
if defined STD goto pick_std_unknown
echo WARNING: %COMPILER% doesn't know %STD_NAME%%CMS_STD% or older standards, so compiling without -std. 1>&2
exit /b 0
:pick_std_unknown
echo %COMPILER% doesn't know --std %STD%. Try an older standard, e.g. --std %STD_EXAMPLE%, or a newer compiler. 1>&2
exit /b 1
:pick_std_found
set "STD_FLAG=-std=%CHOSEN%"
if defined MSVC set "STD_FLAG=/std:%CHOSEN%"
if defined STD exit /b 0
rem Warn if CHOSEN isn't one of the names of the CMS standard.
set "CANDIDATES=c++latest"
call :std_alias %CMS_STD%
for %%V in (%CMS_STD% %ALIAS%) do call :add_std %%V
set "IS_CMS="
for %%S in (%CANDIDATES%) do if /i "%%S"=="%CHOSEN%" set IS_CMS=1
if defined IS_CMS exit /b 0
echo WARNING: %COMPILER% doesn't know %STD_NAME%%CMS_STD%, which CMS uses, so compiling with %STD_FLAG%. If your code needs %STD_NAME%%CMS_STD%, use a newer compiler. 1>&2
exit /b 0

rem Add the GNU (unless KIND is standard) and standard names of version %1,
rem e.g. gnu++17 and c++17, to CANDIDATES.
:add_std
if "%KIND%"=="gnu" set "CANDIDATES=%CANDIDATES% %GNU_PREFIX%%~1"
set "CANDIDATES=%CANDIDATES% %STD_LANG%%~1"
goto :eof

rem Set ALIAS to the other name of standard %1, e.g. 2a for C++20, which
rem compilers that are too old for the final name know.
:std_alias
set "ALIAS="
if "%STD_LANG% %~1"=="c++ 23" set "ALIAS=2b"
if "%STD_LANG% %~1"=="c++ 20" set "ALIAS=2a"
if "%STD_LANG% %~1"=="c++ 17" set "ALIAS=1z"
if "%STD_LANG% %~1"=="c++ 14" set "ALIAS=1y"
if "%STD_LANG% %~1"=="c++ 11" set "ALIAS=0x"
if "%STD_LANG% %~1"=="c 11" set "ALIAS=1x"
if "%STD_LANG% %~1"=="c 99" set "ALIAS=9x"
goto :eof

rem Set CHOSEN to %1 if COMPILER knows that standard. cl only warns (D9002)
rem about a /std it doesn't know, and clang-cl about an unknown argument.
:try_std
if defined MSVC goto try_std_msvc
"%COMPILER%" -std=%~1 -x %STD_LANG% -fsyntax-only - <nul >nul 2>nul
set "PROBE=%ERRORLEVEL%"
if "%PROBE%"=="9009" set "NOT_FOUND=1"
if "%PROBE%"=="0" set "CHOSEN=%~1"
goto :eof
:try_std_msvc
set "CHECK=%STD_CHECK%.cpp"
if "%STD_LANG%"=="c" set "CHECK=%STD_CHECK%.c"
type nul >"%CHECK%"
"%COMPILER%" /nologo /std:%~1 /Zs "%CHECK%" >"%STD_CHECK%.log" 2>&1
set "PROBE=%ERRORLEVEL%"
if "%PROBE%"=="9009" set "NOT_FOUND=1"
if not "%PROBE%"=="0" goto :eof
findstr /i /c:"D9002" /c:"unknown argument" "%STD_CHECK%.log" >nul
if errorlevel 1 set "CHOSEN=%~1"
goto :eof

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
echo Unknown option %~1. The options are --tests, --timeout and --std. 1>&2
exit /b 1

:limit_bad
echo --timeout needs a number of seconds, e.g. --timeout 10 1>&2
exit /b 1

:std_bad
echo --std needs a C++ or C standard, e.g. --std 17, --std c++17, --std gnu++17 or --std c99 1>&2
exit /b 1

:std_mode
echo --std only works with cpp and c. 1>&2
exit /b 1

:limit_needs_powershell
echo --timeout needs PowerShell, which comes with Windows 10 and 11. 1>&2
exit /b 1
