WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

COPY ./app /app

ENV PYTHONPATH=/app

CMD ["sh", "-c", "python -m db.init_db && uvicorn app.main:app --host 0.0.0.0 --port 8000"]