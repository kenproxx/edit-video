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
    from decimal import Decimal
    if not math.isfinite(seconds) or seconds < 0: raise ValueError("Thời gian không hợp lệ")
    minutes, rest = divmod(int(Decimal(str(seconds))*1000),60000)
    whole, fraction = divmod(rest,1000)
    return f'{minutes:02d}:{whole:02d}.{fraction:03d}'.rstrip('0').rstrip('.')


def source_interval(options,duration):
    start=options.trim_start
    end=duration if options.trim_end is None else options.trim_end
    if not all(math.isfinite(v) for v in (start,end,duration)) or duration<=0 or start<0:
        raise ValueError('Đoạn cắt cần thời gian hữu hạn, không âm và video hợp lệ')
    if options.trim_end is not None and end<=start:
        raise ValueError('Đoạn cắt cần mốc tới lớn hơn mốc từ')
    # A valid requested interval that does not fit this source leaves it whole.
    # Keep this decision shared by validation, preview, audio and batch export.
    if end>duration or start>=duration: return 0,duration
    return start,end


def trimmed_duration(options,duration):
    start,end=source_interval(options,duration)
    return (end-start)/options.speed
