FROM python:3.11

WORKDIR /app

COPY requirements.txt .

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

CMD ["sh", "-c", "python db/init_db.py && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
