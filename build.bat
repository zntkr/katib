@echo off
setlocal
cd /d "%~dp0"
echo ===================================================
echo Katib Paketleme ve Kurulum (Setup) Olusturucu
echo ===================================================

:: Derleme her zaman projenin kendi sanal ortamindan (.venv) yapilir; paketlenen sey
:: yalniz requirements*.txt ve constraints.txt'te yazan surumlerdir (ADR-0011).
:: Python surumu tek yerde yazar: .python-version
set /p PY_VERSION=<.python-version
set VENV_PY=.venv\Scripts\python.exe

:: "build.bat gpu": ayni program + NVIDIA cuBLAS; NVIDIA kartli makinede CUDA kurmadan GPU'da
:: calisir (plan 0009 Faz 2). Arguman yoksa normal (yalniz CPU) paket.
set "KATIB_GPU="
set "ISCC_GPU="
if /i "%~1"=="gpu" (
    set "KATIB_GPU=1"
    set "ISCC_GPU=/DGpu=1"
    echo Paket: GPU ^(NVIDIA cuBLAS dahil^)
) else (
    echo Paket: normal ^(yalniz CPU^)
)

echo.
echo [1/3] Sanal ortam hazirlaniyor (Python %PY_VERSION%)...
if not exist %VENV_PY% py -%PY_VERSION% -m venv .venv
if not exist %VENV_PY% (
    echo [HATA] Sanal ortam kurulamadi. Python %PY_VERSION% kurulu mu? ^(py -0p ile bakin^)
    pause
    exit /b 1
)
%VENV_PY% -m pip install --disable-pip-version-check -q -r requirements.txt -r requirements-dev.txt -c constraints.txt
if %ERRORLEVEL% NEQ 0 (
    echo [HATA] Bagimliliklar kurulamadi!
    pause
    exit /b %ERRORLEVEL%
)
if defined KATIB_GPU (
    %VENV_PY% -m pip install --disable-pip-version-check -q -r requirements-gpu.txt -c constraints.txt
    if errorlevel 1 (
        echo [HATA] GPU kitapligi ^(requirements-gpu.txt^) kurulamadi!
        pause
        exit /b 1
    )
)
echo [OK] Sanal ortam hazir.

echo.
echo [2/3] PyInstaller ile uygulama paketleniyor...
:: PyInstaller, paketledigi DLL'lerin bagimliliklarini PATH'teki klasorlerde de arar ve buldugunu
:: pakete koyar: Poppler, Git, Conda gibi araclarin DLL'leri boyle sizar (plan 0015: Poppler'in
:: ICU 78'i Qt'yi acilista dusurdu). Paketleme yalniz Windows klasorlerini gorur; .venv'in
:: Python'u tam yoluyla cagrildigi icin PATH'e gerek yok. setlocal sayesinde PATH betik bitince doner.
set "PATH=%SystemRoot%\System32;%SystemRoot%;%SystemRoot%\System32\Wbem"
%VENV_PY% -m PyInstaller Katib.spec --clean -y
if %ERRORLEVEL% NEQ 0 (
    echo [HATA] PyInstaller paketlemesi basarisiz oldu!
    pause
    exit /b %ERRORLEVEL%
)
echo [OK] PyInstaller islemi tamamlandi.

echo.
echo [3/3] Inno Setup ile Setup.exe olusturuluyor...
:: Inno Setup 6 ve 7 icin olasi yollari kontrol edelim
set ISCC=""
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set ISCC="%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files\Inno Setup 7\ISCC.exe" set ISCC="C:\Program Files\Inno Setup 7\ISCC.exe"
if exist "C:\Program Files (x86)\Inno Setup 7\ISCC.exe" set ISCC="C:\Program Files (x86)\Inno Setup 7\ISCC.exe"

if not %ISCC%=="" (
    %ISCC% %ISCC_GPU% Katib.iss
    if %ERRORLEVEL% NEQ 0 (
        echo [HATA] Inno Setup derlemesi basarisiz oldu!
        pause
        exit /b %ERRORLEVEL%
    )
    echo [OK] Kurulum dosyasi basariyla olusturuldu ^(installer/ klasorunu kontrol edin^).
) else (
    echo [UYARI] Inno Setup Compiler ^(ISCC.exe^) bulunamadi.
    echo Lutfen Inno Setup'i kurun veya 'Katib.iss' dosyasina cift tiklayip kendiniz 'Compile' yapin.
)

echo.
echo ===================================================
echo Islem Tamamlandi!
echo ===================================================
pause
