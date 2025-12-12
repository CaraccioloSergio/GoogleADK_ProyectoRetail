Write-Host "🛑 Deteniendo Milo DEV..."

$ports = @(8000, 8001, 9000)

foreach ($port in $ports) {
    $pids = netstat -ano | Select-String ":$port " | ForEach-Object {
        ($_ -split '\s+')[-1]
    } | Select-Object -Unique

    foreach ($pid in $pids) {
        if ($pid -and $pid -ne "0") {
            Write-Host "🔪 Matando proceso PID $pid (puerto $port)"
            taskkill /PID $pid /F | Out-Null
        }
    }
}

# Ngrok (si está corriendo)
Get-Process ngrok -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Host "🔪 Cerrando ngrok (PID $($_.Id))"
    $_ | Stop-Process -Force
}

Write-Host "✅ Milo DEV detenido."
