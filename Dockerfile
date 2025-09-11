FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY utils/ /app/utils/
COPY managers/ /app/managers/
COPY clients/ /app/clients/
COPY middlewares/ /app/middlewares/
COPY routers/ /app/routers/
COPY models/ /app/models/
COPY states/ /app/states/
COPY bot.py /app/bot.py
COPY config.py /app/config.py

CMD ["python", "bot.py"]
