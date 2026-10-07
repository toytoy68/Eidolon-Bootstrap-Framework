# G046 harness: wrapper.ps1 <Standard|Legacy> <script.ps1> <script arguments...>
# Legacy reproduces the native-argument quoting of Windows PowerShell 5.1.
$PSNativeCommandArgumentPassing = $args[0]
$target = $args[1]
$rest = @($args | Select-Object -Skip 2)
& $target @rest
exit $LASTEXITCODE
