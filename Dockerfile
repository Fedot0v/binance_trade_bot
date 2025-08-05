<<<<<<< HEAD
FROM python:3.11

=======
>>>>>>> 31d83bcb6c9f1475c11a8cd590fba98b723106e4
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
=======
COPY ./app /app
>>>>>>> 31d83bcb6c9f1475c11a8cd590fba98b723106e4
