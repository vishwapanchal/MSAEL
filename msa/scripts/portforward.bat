@echo off
rem Self-reconnecting port-forward. kubectl port-forward exits when its pod is replaced,
rem which happens on every pod kill, so this loop starts it again until the window is closed.
rem Usage: portforward.bat NAMESPACE SERVICE LOCAL_PORT SERVICE_PORT
:loop
kubectl -n %1 port-forward svc/%2 %3:%4
timeout /t 1 /nobreak >nul
goto loop
