FROM python:3.8-slim

RUN pip install --upgrade pip

WORKDIR /code

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . .

EXPOSE 8080

ENV PORT=8080

ENV BINANCE_API_KEY=${BINANCE_API_KEY}

ENV BINANCE_API_SECRET=${BINANCE_API_SECRET}

CMD ["python", "main.py"]