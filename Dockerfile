FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY nova_tg.py .
CMD ["python", "nova_tg.py"]