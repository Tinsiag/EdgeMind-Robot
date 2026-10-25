[CmdletBinding()]
param(
    [ValidateSet('check', 'prepare', 'mapping', 'test', 'build', 'launch')]
    [string]$Action = 'check',
    [ValidateSet('motion', 'fusion', 'all')]
    [string]$Project = 'motion',
    [string]$GowinHome = $env:GOWIN_HOME,
    [string]$Examples,
    [switch]$SensorsOnly
)

$ErrorActionPreference = 'Stop'
$cameraRoot = $PSScriptRoot
$repositoryRoot = [IO.Path]::GetFullPath((Join-Path $cameraRoot '..\..'))
$python = Join-Path $cameraRoot '.venv\Scripts\python.exe'
$simulationBin = Join-Path $repositoryRoot 'tmp\vision-motion-tools\bin'
if (-not $GowinHome) { $GowinHome = 'C:\Gowin\Gowin_V1.9.12.04_x64' }
if (-not $Examples) {
    $Examples = Join-Path $cameraRoot '.local\environment\examples\GW5AT60K'
}
$gowin = Join-Path $GowinHome 'IDE\bin\gw_sh.exe'
$simulationLibrary = Join-Path $GowinHome 'IDE\simlib\gw5a\prim_sim.v'
$selected = switch ($Project) {
    'motion' { @('a741-imu-motion') }
    'fusion' { @('a741-fpga-fusion') }
    'all' { @('a741-imu-motion', 'a741-fpga-fusion') }
}

function Require-Path([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { throw "Missing development dependency: $Path" }
}

function Invoke-ProjectPython([string[]]$PythonArguments) {
    & $python -X utf8 @PythonArguments
    if ($LASTEXITCODE -ne 0) { throw "Python command failed with exit code $LASTEXITCODE" }
}

Require-Path $python
if ($Action -eq 'launch' -and $Project -eq 'all') {
    throw 'Choose one project when launching the GUI.'
}
$previousPath = $env:PATH
$previousGowin = $env:GOWIN_HOME
try {
    $env:PATH = "$(Split-Path $python);$simulationBin;$(Split-Path $gowin);$previousPath"
    $env:GOWIN_HOME = $GowinHome
    if ($Action -eq 'check') {
        Require-Path (Join-Path $simulationBin 'iverilog.exe')
        Require-Path (Join-Path $simulationBin 'vvp.exe')
        Require-Path $gowin
        Require-Path $simulationLibrary
        Require-Path $Examples
        Invoke-ProjectPython -PythonArguments @('--version')
        Invoke-ProjectPython -PythonArguments @('-m', 'pip', 'check')
        Invoke-ProjectPython -PythonArguments @('-m', 'pip', 'freeze')
        Write-Output "Gowin: $gowin"
        Write-Output "Icarus: $simulationBin"
        Write-Output "Examples: $Examples"
        foreach ($name in $selected) {
            Require-Path (Join-Path $cameraRoot "$name\.local\mapping\edgemind_slam.dll")
            Require-Path (Join-Path $cameraRoot "$name\.local\platform-motion-lidar\dvi_encoder.v")
        }
        Write-Output 'PASS: development dependencies are available. Board acceptance is separate.'
        return
    }
    foreach ($name in $selected) {
        Push-Location (Join-Path $cameraRoot $name)
        try {
            $variant = if ($name -eq 'a741-fpga-fusion') { @('--fusion', '--tft480', '--route-option', '2', '--place-option', '1') } else { @('--motion-lidar') }
            Write-Output "$name / $Action"
            switch ($Action) {
                'prepare' {
                    Require-Path $Examples
                    Invoke-ProjectPython -PythonArguments (@('scripts/build.py', 'prepare') + $variant + @('--examples', $Examples))
                }
                'mapping' { Invoke-ProjectPython -PythonArguments @('scripts/setup_mapping.py') }
                'test' {
                    Require-Path (Join-Path $simulationBin 'iverilog.exe')
                    Require-Path $simulationLibrary
                    Invoke-ProjectPython -PythonArguments @('-u', 'scripts/check.py')
                }
                'build' {
                    Require-Path $gowin
                    Require-Path $Examples
                    Invoke-ProjectPython -PythonArguments (@('-u', 'scripts/build.py', 'build') + $variant +
                        @('--examples', $Examples, '--gowin', $gowin))
                }
                'launch' {
                    $launchArguments = @('host/app.py')
                    if ($SensorsOnly) { $launchArguments += '--sensors-only' }
                    Invoke-ProjectPython -PythonArguments $launchArguments
                }
            }
        } finally { Pop-Location }
    }
} finally {
    $env:PATH = $previousPath
    $env:GOWIN_HOME = $previousGowin
}
