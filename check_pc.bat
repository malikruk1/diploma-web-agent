@echo off
cd /d "%~dp0"
echo Checking PC... 
powershell -NoProfile -Command "$o=@(); $o+='CPU: '+(Get-CimInstance Win32_Processor).Name; $o+='RAM_GB: '+[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB,1); foreach($g in Get-CimInstance Win32_VideoController){$o+='GPU: '+$g.Name+' | AdapterRAM_GB(may be capped at 4): '+[math]::Round($g.AdapterRAM/1GB,1)}; try{$v=Get-ItemProperty 'HKLM:\SYSTEM\ControlSet001\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}\0*' -ErrorAction SilentlyContinue | Where-Object {$_.'HardwareInformation.qwMemorySize'}; foreach($x in $v){$o+='VRAM_GB: '+$x.DriverDesc+' = '+[math]::Round($x.'HardwareInformation.qwMemorySize'/1GB,1)}}catch{}; foreach($d in Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3'){$o+='Disk '+$d.DeviceID+' free_GB: '+[math]::Round($d.FreeSpace/1GB,1)}; $o+='Python: '+(& python --version 2>&1); $o | Out-File -Encoding utf8 pc_info.txt; $o"
where nvidia-smi >nul 2>&1 && nvidia-smi --query-gpu=name,memory.total --format=csv >> pc_info.txt
echo.
echo Done. Saved to pc_info.txt
pause
