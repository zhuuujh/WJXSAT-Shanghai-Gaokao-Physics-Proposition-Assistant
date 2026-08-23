@echo off
title Physics Exam Assistant
pushd "%~dp0"
echo.
echo  ============================================
echo     上海物理等级考智能命题助手
echo  ============================================
echo.
echo  正在启动，浏览器将自动打开 http://localhost:8501
echo  关闭此窗口 = 关闭程序
echo.
"%USERPROFILE%\AppData\Local\Programs\Python\Python313\python.exe" -m streamlit run app.py
echo.
echo  程序已退出
pause
