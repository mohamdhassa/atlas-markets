"""Explicit timezone parsing shared by live and durable IBKR reporting."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def execution_time_ms(row,default_timezone='Etc/UTC'):
 for key in ('time','executed_at','execution_time','timestamp','datetime'):
  value=row.get(key)
  if value in (None,''):continue
  if isinstance(value,(int,float)):
   number=int(value);return number*1000 if number and number<10_000_000_000 else number
  text=' '.join(str(value).split())
  if text.isdigit():
   number=int(text);return number*1000 if number and number<10_000_000_000 else number
  try:
   parsed=datetime.fromisoformat(text.replace('Z','+00:00'))
  except ValueError:
   parts=text.split(' ')
   zone_name=parts.pop() if len(parts)==3 else None
   parsed=None
   for fmt in ('%Y%m%d %H:%M:%S','%Y%m%d-%H:%M:%S'):
    try:parsed=datetime.strptime(' '.join(parts),fmt);break
    except ValueError:pass
   if parsed is None:continue
   if zone_name:
    try:parsed=parsed.replace(tzinfo=ZoneInfo({'US/Eastern':'America/New_York'}.get(zone_name,zone_name)))
    except ZoneInfoNotFoundError:continue
  if parsed.tzinfo is None:
   # Legacy execution callbacks omit a zone; use the declared Gateway zone,
   # never the web server's local timezone. Hyphen format explicitly means UTC.
   zone_name='UTC' if len(text)>8 and text[8]=='-' else row.get('time_timezone') or default_timezone
   try:parsed=parsed.replace(tzinfo=ZoneInfo({'US/Eastern':'America/New_York'}.get(zone_name,zone_name)))
   except ZoneInfoNotFoundError:continue
  if parsed.utcoffset()!=parsed.replace(fold=1).utcoffset():continue
  utc=parsed.astimezone(timezone.utc)
  if utc.astimezone(parsed.tzinfo).replace(tzinfo=None)!=parsed.replace(tzinfo=None):continue
  return int(utc.timestamp()*1000)
 return 0
