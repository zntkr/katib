@echo off
setlocal

:: Terminalde "python" komutu calismiyorsa tam yolu buraya yaziyoruz:
set PYTHON_EXE=C:\Python314\python.exe

echo [1/1] PyInstaller ile CPU-Only paketleniyor...
"%PYTHON_EXE%" -m PyInstaller Katib.spec --clean
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [HATA] PyInstaller paketlemesi basarisiz oldu! Islemler durduruluyor.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo [OK] Tamamlandi! dist\Dikte klasorunu zipleyip dagitabilirsiniz.
pause