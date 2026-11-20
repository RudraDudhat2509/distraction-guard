# Distraction Guard demo launcher. Run on the laptop, in PowerShell:  .\launch_demo.ps1
# Needs: Jetson powered on, USB-C cable from the Jetson's USB-C port to the laptop, Uno plugged into the Jetson.

$key = "$env:USERPROFILE\.ssh\jetson_ed25519"
$jetson = "ruruvatsal@192.168.55.1"
$dashboard = Join-Path $PSScriptRoot "dashboard\dashboard.py"

Write-Host "1/4 Checking the link to the Jetson..."
if (-not (Test-Connection 192.168.55.1 -Count 2 -Quiet)) {
    Write-Host "Jetson not reachable. Check its power, replug the USB-C cable, wait 60 s, try again." -ForegroundColor Red
    exit 1
}

Write-Host "2/4 Starting the guard program on the Jetson..."
ssh -i $key -o StrictHostKeyChecking=accept-new $jetson "~/guard/stop.sh; ~/guard/start.sh"

Write-Host "3/4 Waiting for the model to load (about 20 s)..."
$ready = $false
for ($i = 0; $i -lt 40; $i++) {
    try {
        $r = Invoke-WebRequest "http://192.168.55.1:8000/status" -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -eq 200) { $ready = $true; break }
    } catch { }
    Start-Sleep 3
}
if (-not $ready) {
    Write-Host "The program did not start. See the exam notes: restart the camera service, then run this again." -ForegroundColor Red
    exit 1
}

Write-Host "4/4 Opening the dashboard..."
$pythonw = (Get-Command pythonw -ErrorAction SilentlyContinue).Source
if (-not $pythonw) { $pythonw = "$env:USERPROFILE\anaconda3\pythonw.exe" }
Start-Process $pythonw -ArgumentList "`"$dashboard`""
Write-Host "Running. Browser view: http://192.168.55.1:8000   To stop: ssh -i $key $jetson '~/guard/stop.sh'" -ForegroundColor Green
