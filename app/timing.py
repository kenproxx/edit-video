"""Source interval input and output timeline shared by UI and engine."""
import math


def parse_time(value: str) -> float:
    text=value.strip().replace(',','.')
    try:
        parts=text.split(':')
        if len(parts)==1: seconds=float(parts[0])*60
        elif len(parts) in (2,3):
            if not all(p and float(p)>=0 for p in parts): raise ValueError
            if any(float(p)>=60 for p in parts[1:]): raise ValueError
            seconds=sum(float(p)*60**i for i,p in enumerate(reversed(parts)))
        else: raise ValueError
        if not math.isfinite(seconds) or seconds<0: raise ValueError
        return seconds
    except ValueError as exc:
        raise ValueError('Thời gian dùng phút:giây (ví dụ 2:30) hoặc số phút') from exc


def format_time(seconds: float) -> str:
    minutes=int(seconds//60)
    rest=seconds-minutes*60
    return f'{minutes:02d}:{rest:06.3f}'.rstrip('0').rstrip('.')


def source_interval(options,duration):
    start=options.trim_start
    end=duration if options.trim_end is None else options.trim_end
    if not all(math.isfinite(v) for v in (start,end,duration)) or not 0<=start<end<=duration:
        raise ValueError('Đoạn cắt cần 0 ≤ từ < tới ≤ thời lượng video nguồn')
    return start,end


def trimmed_duration(options,duration):
    start,end=source_interval(options,duration)
    return (end-start)/options.speed
