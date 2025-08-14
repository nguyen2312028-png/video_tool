@echo off
title Build Tool Video (OneFile) with Nuitka
echo ==========================================
echo  Cài thư viện cần thiết...
echo ==========================================
pip install nuitka ordered-set zstandard

echo.
echo ==========================================
echo  Building single EXE file...
echo ==========================================

REM Thay tool_video.py thành tên file Python của bạn
nuitka tool_video.py ^
--onefile ^
--standalone ^
--mingw64 ^
--enable-plugin=numpy ^
--include-data-files=ffmpeg.exe=ffmpeg.exe ^
--include-module=moviepy ^
--include-module=moviepy.editor ^
--output-dir=dist_tool

echo.
echo ==========================================
echo  Build xong! EXE nằm trong thư mục:
echo  dist_tool
echo ==========================================
pause
