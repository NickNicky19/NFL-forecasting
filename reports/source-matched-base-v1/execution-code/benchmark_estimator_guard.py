"""Pure independent native-fit limit check; no source/model work."""
import math
FIELDS={'active','pid','process_start_ticks','process_cpu_start','cpu_clock','monotonic_start','attempt','max_wall_seconds','max_CPU_seconds','generated_at'}
def guard_reason(marker,*,child_pid,process_start_ticks,cpu_now,monotonic_now,previous_attempt=0):
    if not isinstance(marker,dict) or set(marker)!=FIELDS:return 'MALFORMED_ESTIMATOR_GUARD',previous_attempt
    if (type(marker['active']) is not bool or type(marker['pid']) is not int or marker['pid']!=child_pid
        or type(marker['process_start_ticks']) is not int or marker['process_start_ticks']!=process_start_ticks
        or type(marker['attempt']) is not int or not max(1,previous_attempt)<=marker['attempt']<=168
        or marker['cpu_clock']!='proc_utime_plus_stime_over_CLK_TCK'
        or marker['max_wall_seconds']!=60 or marker['max_CPU_seconds']!=90
        or not isinstance(marker['generated_at'],str) or not marker['generated_at']):
        return 'INVALID_ESTIMATOR_GUARD_IDENTITY_OR_LIMITS',previous_attempt
    for name in ('process_cpu_start','monotonic_start'):
        value=marker[name]
        if type(value) not in (int,float) or not math.isfinite(value) or value<0:
            return 'INVALID_ESTIMATOR_GUARD_CLOCK',previous_attempt
    if marker['process_cpu_start']>cpu_now+.03 or marker['monotonic_start']>monotonic_now+.1:
        return 'FUTURE_ESTIMATOR_GUARD_CLOCK',previous_attempt
    attempt=marker['attempt']
    if marker['active']:
        if monotonic_now-marker['monotonic_start']>=58.5:return 'PER_ESTIMATOR_WALL_LIMIT',attempt
        if cpu_now-marker['process_cpu_start']>=88.5:return 'PER_ESTIMATOR_CPU_LIMIT',attempt
    return None,attempt
