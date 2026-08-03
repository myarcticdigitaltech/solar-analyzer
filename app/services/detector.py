from typing import Any
import pandas as pd
from fastapi import HTTPException
KEYWORDS={"time":["time","datetime","date time","timestamp","วันที่","เวลา"],"solar_dc":["total dc power","pv dc power","solar dc power","dc power"],"active_power":["total active power","active power","ac output","inverter output"],"battery_charge":["battery charging power","charging power","battery charge"],"battery_discharge":["battery discharging power","discharging power","battery discharge"]}
def norm(v:Any)->str: return " ".join(str(v).lower().split())
def detect_columns(df:pd.DataFrame)->dict[str,str|None]:
    cols=list(df.columns)
    out={}
    for key,kws in KEYWORDS.items():
        out[key]=next((c for kw in kws for c in cols if kw in norm(c)),None)
    missing=[label for key,label in {"time":"วันและเวลา","solar_dc":"Total DC Power","active_power":"Total Active Power"}.items() if not out[key]]
    if missing: raise HTTPException(status_code=400, detail="ไม่พบคอลัมน์ที่จำเป็น: "+", ".join(missing))
    return out
