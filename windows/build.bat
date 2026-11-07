@echo off
rem SetIP Windows 版打包脚本
rem 前提：已安装 Python 3.8+（勾选 Add to PATH）

cd /d %~dp0

python -m pip install --upgrade pyyaml pyinstaller || goto :error
python -m py_compile setip_windows.py || goto :error
rem config.yaml 打进 exe（首次运行自动释放到 %%APPDATA%%\SetIP\config.yaml）
python -m PyInstaller --onefile --name SetIP --clean -y --add-data "config.yaml;." setip_windows.py || goto :error

echo.
echo 打包完成: dist\SetIP.exe
echo 直接双击 SetIP.exe 即可，配置已内置（首次运行释放到 %%APPDATA%%\SetIP\config.yaml）。
pause
exit /b 0

:error
echo 打包失败，请检查上方错误信息。
pause
exit /b 1
