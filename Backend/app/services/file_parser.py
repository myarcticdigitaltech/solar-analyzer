from io import BytesIO
import pandas as pd

async def parse_uploaded_file(file):

    content = await file.read()

    filename = file.filename.lower()

    if filename.endswith(".csv"):

        try:
            df = pd.read_csv(BytesIO(content), encoding="utf-8")

        except:

            df = pd.read_csv(BytesIO(content), encoding="cp874")

    else:

        df = pd.read_excel(BytesIO(content))

    return df