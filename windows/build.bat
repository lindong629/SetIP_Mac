@echo off
rem SetIP Windows 版打包脚本
rem 前提：已安装 Python 3.8+（勾选 Add to PATH）

cd /d %~dp0

python -m pip install --upgrade pyyaml pyinstaller || goto :error
python -m py_compile setip_windows.py || goto :error
python -m PyInstaller --onefile --name SetIP --clean -y setip_windows.py || goto :error

echo.
echo 打包完成: dist\SetIP.exe
echo 把 SetIP.exe 和 config.yaml 放在同一个文件夹，双击 SetIP.exe 即可使用。
pause
exit /b 0

:error
echo 打包失败，请检查上方错误信息。
pause
exit /b 1
