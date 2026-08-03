from fastapi import APIRouter, File, UploadFile
from app.services.file_parser import parse_uploaded_file
from app.services.detector import detect_columns
from app.services.normalizer import normalize_dataframe
from app.services.calculator import calculate_analysis
router = APIRouter(prefix="/api", tags=["Analysis"])
@router.post("/analyze")
async def analyze_file(file: UploadFile = File(...)):
    if not file.filename:
        return {"status":"error","message":"ไม่พบชื่อไฟล์"}
    content = await file.read()
    dataframe = parse_uploaded_file(file.filename, content)
    detected = detect_columns(dataframe)
    normalized = normalize_dataframe(dataframe, detected)
    result = calculate_analysis(normalized)
    return {"status":"completed","file":{"name":file.filename,"content_type":file.content_type,"size_bytes":len(content)},"data_quality":{"source_rows":len(dataframe),"valid_rows":len(normalized),"detected_columns":detected},**result}
