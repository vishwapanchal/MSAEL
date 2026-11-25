@echo off
setlocal EnableExtensions
cd /d "%~dp0\..\.."
set NS=boutique-staging
set DEP=deployment/reviews-service

echo ============================================================
echo  Rolling update demo: reviews-service 1.0.0 to 1.1.0 and back
echo ============================================================
echo NOTE: run.bat keeps a port-forward on localhost 8081 bound to ONE pod.
echo This demo needs 8081 too, so it closes the window titled boutique-reviews first
echo and restarts it at the end. After any rollout the old port-forward is stale,
echo so it must always be restarted.
echo.
pause

echo [0/7] Closing the old reviews port-forward window if present
taskkill /fi "WINDOWTITLE eq boutique-reviews*" /f /t >nul 2>&1

echo [1/7] Building image reviews-service:1.1.0 inside minikube
minikube image build -t reviews-service:1.1.0 --build-opt=build-arg=APP_VERSION=1.1.0 msa\services\reviews-service
if errorlevel 1 goto fail

echo [2/7] Current image and revision
kubectl -n %NS% get %DEP% -o wide
kubectl -n %NS% rollout history %DEP%
pause

echo [3/7] Updating the image to reviews-service:1.1.0
kubectl -n %NS% set image %DEP% reviews-service=reviews-service:1.1.0
if errorlevel 1 goto fail

echo [4/7] Waiting for the rollout to finish
kubectl -n %NS% rollout status %DEP% --timeout=180s
if errorlevel 1 goto fail

echo [5/7] Checking /version through a temporary port-forward on 8081
call :showversion
pause

echo [6/7] Rolling back with kubectl rollout undo
kubectl -n %NS% rollout undo %DEP%
if errorlevel 1 goto fail
kubectl -n %NS% rollout status %DEP% --timeout=180s
if errorlevel 1 goto fail

echo [7/7] Checking /version again, expecting 1.0.0
call :showversion

echo Restarting the reviews port-forward window on 8081
start "boutique-reviews" cmd /c "kubectl -n %NS% port-forward svc/reviews-service 8081:8080"
echo.
echo Demo finished.
exit /b 0

:showversion
start "rollout-pf" /min cmd /c "kubectl -n %NS% port-forward svc/reviews-service 8081:8080"
timeout /t 5 /nobreak >nul
curl -s http://localhost:8081/version
echo.
taskkill /fi "WINDOWTITLE eq rollout-pf*" /f /t >nul 2>&1
exit /b 0

:fail
echo.
echo ERROR: a step failed. Showing pods for diagnosis.
kubectl -n %NS% get pods
exit /b 1
