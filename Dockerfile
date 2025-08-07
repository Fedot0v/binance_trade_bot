FROM python:3.11

WORKDIR /app/app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt


ENV PYTHONPATH=/app/app

CMD ["python", "main.py"]