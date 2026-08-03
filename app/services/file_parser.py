from io import BytesIO
from pathlib import Path
import pandas as pd
from fastapi import HTTPException
SUPPORTED_EXTENSIONS={".csv",".xlsx",".xls"}
def parse_uploaded_file(filename:str, content:bytes)->pd.DataFrame:
    ext=Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="รองรับเฉพาะไฟล์ CSV, XLSX และ XLS")
    try:
        if ext==".csv":
            df=None
            for enc in ("utf-8-sig","utf-8","cp874","latin1"):
                try:
                    df=pd.read_csv(BytesIO(content),encoding=enc); break
                except Exception:
                    pass
            if df is None: raise ValueError("ไม่สามารถอ่าน CSV ได้")
        else:
            df=pd.read_excel(BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"ไม่สามารถอ่านไฟล์ได้: {e}") from e
    if df.empty: raise HTTPException(status_code=400, detail="ไม่พบข้อมูลในไฟล์")
    df.columns=[" ".join(str(c).strip().split()) for c in df.columns]
    return df
