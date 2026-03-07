FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    rust-all \
    cargo \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-u", "main.py"]
```

Commit ✅

---

**צעד 2 — עדכן `requirements.txt`**

מחק הכל והדבק:
```
flask==3.0.3
python-dotenv==1.0.1
crewai
crewai-tools
supabase
sendgrid
jinja2
requests
