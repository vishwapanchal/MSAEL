@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set NS=boutique-staging
set NEWINSTALL=0

if /i "%~1"=="claude" goto mode_claude
if /i "%~1"=="stop" goto mode_stop
if /i "%~1"=="clean" goto mode_clean
if /i "%~1"=="demo" goto mode_demo
goto mode_run

:mode_demo
rem Scenario: rolling update 1.0.0 to 1.1.0 then rollback (needs a running cluster)
call "%~dp0msa\scripts\rollout_demo.bat"
exit /b %errorlevel%

:mode_claude
where claude >nul 2>&1
if errorlevel 1 goto claude_missing
if not exist "MASTER_PROMPT.md" goto prompt_missing
claude "Read MASTER_PROMPT.md in full and execute it exactly"
exit /b %errorlevel%
:claude_missing
echo ERROR: the claude command was not found in PATH. Install Claude Code first.
exit /b 1
:prompt_missing
echo ERROR: MASTER_PROMPT.md was not found next to run.bat.
exit /b 1

:mode_stop
echo Stopping port-forwards and minikube
taskkill /im kubectl.exe /f >nul 2>&1
minikube stop
exit /b 0

:mode_clean
echo Deleting the minikube cluster
taskkill /im kubectl.exe /f >nul 2>&1
minikube delete
exit /b 0

:mode_run
echo ============================================================
echo  Online Boutique + reviews-service: one-click setup
echo ============================================================

echo [1/8] Checking tools
call :need git Git.Git
call :need docker Docker.DockerDesktop
call :need kubectl Kubernetes.kubectl
call :need minikube Kubernetes.minikube
if "%NEWINSTALL%"=="1" goto reopen
goto docker_check

:reopen
echo.
echo Some tools were just installed. Open a NEW terminal window and run run.bat again.
exit /b 0

:need
where %1 >nul 2>&1
if not errorlevel 1 exit /b 0
where winget >nul 2>&1
if errorlevel 1 goto need_nowinget
echo Installing %1 via winget
winget install -e --id %2 --accept-source-agreements --accept-package-agreements
set NEWINSTALL=1
exit /b 0
:need_nowinget
echo ERROR: %1 is missing and winget is not available. Install it manually.
exit 1

:docker_check
echo [2/8] Checking Docker
docker info >nul 2>&1
if not errorlevel 1 goto docker_ok
echo Docker is not running. Starting Docker Desktop
start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
set /a WAITED=0
:docker_wait
timeout /t 5 /nobreak >nul
docker info >nul 2>&1
if not errorlevel 1 goto docker_ok
set /a WAITED+=5
if %WAITED% GEQ 300 goto docker_fail
echo Waiting for Docker, %WAITED% seconds so far
goto docker_wait
:docker_fail
echo ERROR: Docker did not become ready within 5 minutes.
exit /b 1
:docker_ok
echo Docker is ready.

echo [3/8] Locating release\kubernetes-manifests.yaml
if exist "release\kubernetes-manifests.yaml" goto repo_ok
if exist "microservices-demo\release\kubernetes-manifests.yaml" goto repo_sub
echo Cloning the upstream repository
git clone https://github.com/GoogleCloudPlatform/microservices-demo.git
if errorlevel 1 goto fail
:repo_sub
cd /d "%~dp0microservices-demo"
:repo_ok

echo [4/8] Starting minikube
minikube status >nul 2>&1
if not errorlevel 1 goto mk_ok
minikube start --driver=docker --cpus=4 --memory=4096
if errorlevel 1 goto mk_fail
goto mk_ok
:mk_fail
echo ERROR: minikube failed to start. Hint: raise Docker Desktop memory to 5GB or more and retry.
exit /b 1
:mk_ok

echo [5/8] Creating namespace and deploying Online Boutique
kubectl create namespace %NS% --dry-run=client -o yaml | kubectl apply -f -
if errorlevel 1 goto fail
kubectl apply -n %NS% -f release\kubernetes-manifests.yaml
if errorlevel 1 goto fail

echo [5b/8] Building the customised frontend with Google branding removed
minikube image build -t frontend-local:1.0.0 src\frontend
if errorlevel 1 goto fail
kubectl -n %NS% set image deployment/frontend server=frontend-local:1.0.0
if errorlevel 1 goto fail

echo [6/8] Building and deploying reviews-service
if not exist "msa\services\reviews-service\Dockerfile" goto no_reviews
minikube image build -t reviews-service:1.0.0 msa\services\reviews-service
if errorlevel 1 goto fail
kubectl apply -k msa\deploy\overlays\staging
if errorlevel 1 goto fail
goto wait_ready
:no_reviews
echo reviews-service Dockerfile not found, skipping that service.

:wait_ready
echo [7/8] Waiting for all deployments, this can take several minutes
kubectl -n %NS% wait --for=condition=available deployment --all --timeout=600s
if errorlevel 1 goto wait_fail
goto forwards
:wait_fail
echo ERROR: deployments did not become available. Current pods:
kubectl get pods -n %NS%
exit /b 1

:forwards
echo [8/8] Starting port-forwards in separate windows
start "boutique-frontend" cmd /c "kubectl -n %NS% port-forward svc/frontend 8080:80"
if not exist "msa\services\reviews-service\Dockerfile" goto after_reviews_pf
start "boutique-reviews" cmd /c "kubectl -n %NS% port-forward svc/reviews-service 8081:8080"
:after_reviews_pf
timeout /t 5 /nobreak >nul
start "" http://localhost:8080

if not exist "msa\services\reviews-service\smoke_test.py" goto summary
python -c "print(1)" >nul 2>&1
if errorlevel 1 goto nopython
echo Running smoke test
python msa\services\reviews-service\smoke_test.py http://localhost:8081
if errorlevel 1 goto smoke_fail
echo SMOKE TEST: PASS
goto summary
:smoke_fail
echo SMOKE TEST: FAIL
goto summary
:nopython
echo Python not available, skipping smoke test.

:summary
echo.
echo ============================================================
echo  Shop:     http://localhost:8080
echo  Reviews:  http://localhost:8081/healthz  and  /version
echo  Stop:     run.bat stop
echo  Clean:    run.bat clean
echo ============================================================
exit /b 0

:fail
echo ERROR: the last step failed. See the messages above.
exit /b 1
