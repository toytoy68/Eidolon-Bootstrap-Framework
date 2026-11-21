"""Targeted persistent NVML collector; mutations serialized with its reads."""
import contextlib,fcntl,json,math,os,time
from pathlib import Path
import pynvml as n
UUID='GPU-REDACTED'
BASE=Path(__file__).resolve().parent
_HANDLE=None
@contextlib.contextmanager
def locked():
    with open('/run/eidolon-v100B-nvml.lock','a') as f:
        deadline=time.monotonic()+2
        while True:
            try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);break
            except BlockingIOError:
                if time.monotonic()>deadline:raise RuntimeError('NVML lock timeout')
                time.sleep(.02)
        try:yield
        finally:fcntl.flock(f,fcntl.LOCK_UN)
def handle():
    global _HANDLE
    if _HANDLE is None:
        n.nvmlInit();_HANDLE=n.nvmlDeviceGetHandleByUUID(UUID)
    got=n.nvmlDeviceGetUUID(_HANDLE)
    if isinstance(got,bytes):got=got.decode()
    if got!=UUID:raise RuntimeError('GPU UUID mismatch')
    return _HANDLE
def field(h,ident):
    f=n.nvmlDeviceGetFieldValues(h,[ident])[0]
    if f.nvmlReturn!=n.NVML_SUCCESS:raise RuntimeError('NVML field failed: '+str(f.nvmlReturn))
    mapping={n.NVML_VALUE_TYPE_DOUBLE:'dVal',n.NVML_VALUE_TYPE_UNSIGNED_INT:'uiVal',n.NVML_VALUE_TYPE_UNSIGNED_LONG:'ulVal',n.NVML_VALUE_TYPE_UNSIGNED_LONG_LONG:'ullVal',n.NVML_VALUE_TYPE_SIGNED_LONG_LONG:'sllVal'}
    if f.valueType not in mapping:raise RuntimeError('Unknown NVML field type')
    age=time.time()-f.timestamp/1e6
    if not -2<=age<=5:raise RuntimeError('Stale HBM field: '+str(age))
    return float(getattr(f.value,mapping[f.valueType]))
def cpu_temp():
    values=[]
    for h in Path('/sys/class/hwmon').glob('hwmon*'):
        if (h/'name').read_text().strip()in ['k10temp','coretemp']:
            for p in h.glob('temp*_label'):
                if p.read_text().strip() in ['Tdie','Package id 0']:values.append(float(p.with_name(p.name.replace('_label','_input')).read_text())/1000)
    if not values:raise RuntimeError('No Tdie')
    return max(values)
def sample():
    with locked():
        h=handle();u=n.nvmlDeviceGetUtilizationRates(h);m=n.nvmlDeviceGetMemoryInfo(h)
        reasons=n.nvmlDeviceGetCurrentClocksThrottleReasons(h)
        d=dict(gpu_c=float(n.nvmlDeviceGetTemperature(h,n.NVML_TEMPERATURE_GPU)),hbm_c=field(h,n.NVML_FI_DEV_MEMORY_TEMP),cpu_c=cpu_temp(),
          gpu_w=n.nvmlDeviceGetPowerUsage(h)/1000,power_limit_w=n.nvmlDeviceGetPowerManagementLimit(h)/1000,
          gpu_util_pct=u.gpu,memory_util_pct=u.memory,vram_mib=m.used/1048576,
          sm_mhz=n.nvmlDeviceGetClockInfo(h,n.NVML_CLOCK_SM),memory_mhz=n.nvmlDeviceGetClockInfo(h,n.NVML_CLOCK_MEM),
          ecc_corrected=n.nvmlDeviceGetTotalEccErrors(h,n.NVML_MEMORY_ERROR_TYPE_CORRECTED,n.NVML_VOLATILE_ECC),
          ecc_uncorrected=n.nvmlDeviceGetTotalEccErrors(h,n.NVML_MEMORY_ERROR_TYPE_UNCORRECTED,n.NVML_VOLATILE_ECC),
          ecc_aggregate_corrected=n.nvmlDeviceGetTotalEccErrors(h,n.NVML_MEMORY_ERROR_TYPE_CORRECTED,n.NVML_AGGREGATE_ECC),
          ecc_aggregate_uncorrected=n.nvmlDeviceGetTotalEccErrors(h,n.NVML_MEMORY_ERROR_TYPE_UNCORRECTED,n.NVML_AGGREGATE_ECC))
        for k,bit in [('hw_thermal',n.nvmlClocksThrottleReasonHwThermalSlowdown),('sw_thermal',n.nvmlClocksThrottleReasonSwThermalSlowdown),('sw_power_cap',n.nvmlClocksThrottleReasonSwPowerCap),('hw_power_brake',n.nvmlClocksThrottleReasonHwPowerBrakeSlowdown)]:d[k]='Active' if reasons&bit else 'Not Active'
        if any(not math.isfinite(v) for v in d.values() if isinstance(v,(float,int))):raise RuntimeError('Nonfinite telemetry')
        if not all(0<=d[k]<150 for k in ['gpu_c','hbm_c','cpu_c']):raise RuntimeError('Implausible temperature')
        d.update(epoch=time.time(),monotonic=time.monotonic(),gpu_uuid=UUID)
        return d
def power(value=None):
    with locked():
        h=handle()
        if value is not None:
            lo,hi=n.nvmlDeviceGetPowerManagementLimitConstraints(h);mw=round(value*1000)
            if not lo<=mw<=hi:raise RuntimeError('Power outside hardware range')
            n.nvmlDeviceSetPowerManagementLimit(h,mw)
        actual=n.nvmlDeviceGetPowerManagementLimit(h)/1000
        if value is not None and abs(actual-value)>.1:raise RuntimeError('Power change not verified')
        return actual
def busy():
    with locked():return bool(n.nvmlDeviceGetComputeRunningProcesses(handle()))
