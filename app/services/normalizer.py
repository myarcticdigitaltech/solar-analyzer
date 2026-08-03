import pandas as pd
from fastapi import HTTPException
def num(series,index):
    if series is None: return pd.Series(0.0,index=index,dtype="float64")
    return pd.to_numeric(series.astype(str).str.replace(",","",regex=False).str.strip(),errors="coerce").fillna(0.0)
def normalize_dataframe(df,detected):
    r=pd.DataFrame(index=df.index)
    r["datetime"]=pd.to_datetime(df[detected["time"]],errors="coerce",dayfirst=True)
    r["solar_dc_kw"]=num(df[detected["solar_dc"]],df.index).clip(lower=0)
    r["active_power_kw"]=num(df[detected["active_power"]],df.index).abs()
    r["battery_charge_kw"]=num(df[detected["battery_charge"]] if detected.get("battery_charge") else None,df.index).clip(lower=0)
    r["battery_discharge_kw"]=num(df[detected["battery_discharge"]] if detected.get("battery_discharge") else None,df.index).clip(lower=0)
    r=r.dropna(subset=["datetime"]).drop_duplicates(subset=["datetime"],keep="last").sort_values("datetime").reset_index(drop=True)
    if r.empty: raise HTTPException(status_code=400,detail="ไม่สามารถอ่านวันและเวลาในไฟล์ได้")
    return r
