$ErrorActionPreference = "Stop"

$serverDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$jarPath = Join-Path $serverDir "server.jar"

if (-not (Test-Path -LiteralPath $jarPath)) {
    throw "server.jar not found. Put the Minecraft server jar in $serverDir first."
}

Set-Location -LiteralPath $serverDir
& java -Xms512M -Xmx1024M -jar $jarPath nogui
