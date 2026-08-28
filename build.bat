@echo off
echo ===================================================
echo Katib Paketleme ve Kurulum (Setup) Olusturucu
echo ===================================================

:: Python komutunu tanimlayin
set PYTHON_CMD=C:\Users\ASUS\AppData\Local\Python\bin\python.exe

echo.
echo [1/2] PyInstaller ile uygulama paketleniyor...
%PYTHON_CMD% -m PyInstaller Katib.spec --clean
if %ERRORLEVEL% NEQ 0 (
    echo [HATA] PyInstaller paketlemesi basarisiz oldu!
    pause
    exit /b %ERRORLEVEL%
)
echo [OK] PyInstaller islemi tamamlandi.

echo.
echo [2/2] Inno Setup ile Setup.exe olusturuluyor...
:: Inno Setup 6 ve 7 icin olasi yollari kontrol edelim
set ISCC=""
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files\Inno Setup 7\ISCC.exe" set ISCC="C:\Program Files\Inno Setup 7\ISCC.exe"
if exist "C:\Program Files (x86)\Inno Setup 7\ISCC.exe" set ISCC="C:\Program Files (x86)\Inno Setup 7\ISCC.exe"

if not %ISCC%=="" (
    %ISCC% Katib.iss
    if %ERRORLEVEL% NEQ 0 (
        echo [HATA] Inno Setup derlemesi basarisiz oldu!
        pause
        exit /b %ERRORLEVEL%
    )
    echo [OK] Kurulum dosyasi basariyla olusturuldu (installer/ klasorunu kontrol edin).
) else (
    echo [UYARI] Inno Setup Compiler (ISCC.exe) bulunamadi.
    echo Lutfen Inno Setup'i kurun veya 'Katib.iss' dosyasina cift tiklayip kendiniz 'Compile' yapin.
)

echo.
echo ===================================================
echo Islem Tamamlandi!
echo ===================================================
pause
