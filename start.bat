@echo off
chcp 65001 >nul
setlocal

set "ROOT=%~dp0"
set "BACKEND_DIR=%~dp0docpilot-backend"
set "FRONTEND_DIR=%~dp0docpilot-front-end"
set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"

echo ========================================
echo            DocPilot 一键启动
echo ========================================
echo.
echo 项目根目录：%ROOT%
echo 后端目录：%BACKEND_DIR%
echo 前端目录：%FRONTEND_DIR%
echo Python：%PYTHON_EXE%
echo.

if not exist "%BACKEND_DIR%\" (
    echo [错误] 后端目录不存在：
    echo %BACKEND_DIR%
    pause
    exit /b 1
)

if not exist "%FRONTEND_DIR%\package.json" (
    echo [错误] 前端目录不存在或缺少 package.json：
    echo %FRONTEND_DIR%\package.json
    pause
    exit /b 1
)

if not exist "%PYTHON_EXE%" (
    echo [错误] 虚拟环境 Python 不存在：
    echo %PYTHON_EXE%
    pause
    exit /b 1
)

if not exist "%FRONTEND_DIR%\node_modules\" (
    echo [提示] 正在安装前端依赖...
    pushd "%FRONTEND_DIR%"
    call npm install

    if errorlevel 1 (
        echo [错误] 前端依赖安装失败。
        popd
        pause
        exit /b 1
    )

    popd
)

echo [1/2] 正在启动 FastAPI 后端...
start "DocPilot Backend" /D "%BACKEND_DIR%" cmd /k ""%PYTHON_EXE%" -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

echo [2/2] 正在启动前端...
start "DocPilot Frontend" /D "%FRONTEND_DIR%" cmd /k "npm run dev"

echo.
echo 启动命令已执行。
echo 后端：http://127.0.0.1:8000
echo 接口文档：http://127.0.0.1:8000/docs
echo.
pause

endlocal