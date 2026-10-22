param([ValidateSet('normal','jvm_pressure','search_degradation')][string]$Name = 'normal')
$port = if ($env:EXPORTER_PORT) { $env:EXPORTER_PORT } else { '9101' }
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:$port/scenario/$Name"
