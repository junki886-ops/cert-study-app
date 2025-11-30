FROM python:3.10-slim

WORKDIR /app

# 시스템 의존성 설치
RUN apt-get update && apt-get install -y \
    git \
    tesseract-ocr \
    poppler-utils \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Python 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 앱 파일 복사
COPY . .

# 환경변수 설정
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV PORT=7860

# 포트 노출
EXPOSE 7860

# Flask 실행
CMD ["python", "-m", "flask", "run", "--host=0.0.0.0", "--port=7860"]
