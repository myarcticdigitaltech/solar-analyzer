import math
import pandas as pd
EFF=0.96; PANEL_YIELD=2.5; PEAK=5.7982; OFF=2.6369; FT=0.1623
def period(h): return 0 if 9<=h<16 else (1 if 16<=h<22 else 2)
def r(v): return round(float(v),2)
def calculate_analysis(df):
    d=df.copy(); gaps=d["datetime"].diff().dt.total_seconds().div(3600); valid=gaps[(gaps>0)&(gaps<=6)]; fallback=float(valid.median()) if not valid.empty else 1.0
    nxt=d["datetime"].shift(-1).sub(d["datetime"]).dt.total_seconds().div(3600); d["interval_hour"]=nxt.where((nxt>0)&(nxt<=fallback*3),fallback)
    d["period"]=d["datetime"].dt.hour.map(period); base=d["datetime"].dt.normalize(); d["analysis_date"]=base.where(d["datetime"].dt.hour>=9,base-pd.Timedelta(days=1))
    d["solar_kwh"]=d["solar_dc_kw"]*d["interval_hour"]; d["usage_kwh"]=d["active_power_kw"]*d["interval_hour"]; d["charge_kwh"]=d["battery_charge_kw"]*d["interval_hour"]; d["discharge_kwh"]=d["battery_discharge_kw"]*d["interval_hour"]
    avail=(d["solar_dc_kw"]-d["battery_charge_kw"]).clip(lower=0)*EFF; d["solar_used_kwh"]=pd.concat([d["active_power_kw"],avail],axis=1).min(axis=1)*d["interval_hour"]
    g=d.groupby(["analysis_date","period"]).agg(solar_kwh=("solar_kwh","sum"),usage_kwh=("usage_kwh","sum"),solar_used_kwh=("solar_used_kwh","sum"),charge_kwh=("charge_kwh","sum"),discharge_kwh=("discharge_kwh","sum")).reset_index()
    daily=[]
    for date in sorted(g["analysis_date"].unique()):
        gg=g[g["analysis_date"]==date]
        def vals(col):
            out=[0.0,0.0,0.0]
            for _,row in gg.iterrows(): out[int(row["period"])]=float(row[col])
            return [r(x) for x in out]
        s,u,su,c,dis=vals("solar_kwh"),vals("usage_kwh"),vals("solar_used_kwh"),vals("charge_kwh"),vals("discharge_kwh")
        cov=min(100,su[0]/u[0]*100) if u[0]>0 else 0
        daily.append({"date_iso":pd.Timestamp(date).date().isoformat(),"solar":s,"usage":u,"solar_used":su,"charge":c,"discharge":dis,"daytime_coverage_percent":r(cov)})
    n=len(daily)
    def avg(key,i): return sum(x[key][i] for x in daily)/n if n else 0
    A=[avg("solar",i) for i in range(3)]; U=[avg("usage",i) for i in range(3)]; Direct=[avg("solar_used",i) for i in range(3)]; Charge=[avg("charge",i) for i in range(3)]; Dis=[avg("discharge",i) for i in range(3)]
    coverage=min(100,Direct[0]/U[0]*100) if U[0]>0 else 0; threshold=max(U[2]*1.5,U[2]+5); abnormal=[x["date_iso"] for x in daily if x["usage"][2]>threshold]
    surplus=max(0,A[0]-Direct[0]-Charge[0]); after16=U[1]+U[2]; uncovered=max(0,U[0]-Direct[0]); panels=math.ceil(uncovered/PANEL_YIELD) if uncovered>1 else 0; cost=(U[0]+U[1])*(PEAK+FT)+U[2]*(OFF+FT)
    return {"site":{"date_from":daily[0]["date_iso"],"date_to":daily[-1]["date_iso"],"day_count":n},"summary":{"average_usage_kwh":r(sum(U)),"average_solar_kwh":r(sum(A)),"daytime_coverage_percent":r(coverage),"estimated_daily_cost":r(cost)},"periods":{"09_16":{"solar_kwh":r(A[0]),"usage_kwh":r(U[0]),"solar_used_kwh":r(Direct[0]),"battery_charge_kwh":r(Charge[0]),"battery_discharge_kwh":r(Dis[0])},"16_22":{"solar_kwh":r(A[1]),"usage_kwh":r(U[1]),"solar_used_kwh":r(Direct[1]),"battery_charge_kwh":r(Charge[1]),"battery_discharge_kwh":r(Dis[1])},"22_09":{"solar_kwh":r(A[2]),"usage_kwh":r(U[2]),"solar_used_kwh":r(Direct[2]),"battery_charge_kwh":r(Charge[2]),"battery_discharge_kwh":r(Dis[2])}},"daily":daily,"recommendations":{"load":"ย้ายโหลดมาใช้กลางวัน" if coverage<90 else "Solar ครอบคลุมโหลดช่วงกลางวันได้ดี","battery":"ควรพิจารณาเพิ่มความจุ Battery" if surplus>=2 and after16>=8 else "ยังไม่จำเป็นต้องเพิ่ม Battery ทันที","night":"ตรวจสอบโหลดกลางคืน" if abnormal else "ยังไม่พบค่ากลางคืนผิดปกติชัดเจน","abnormal_night_dates":abnormal},"panel":{"recommended_count":panels,"uncovered_daytime_kwh":r(uncovered),"assumed_panel_daily_yield_kwh":PANEL_YIELD},"formula":{"version":"v1.1","inverter_efficiency":EFF}}
