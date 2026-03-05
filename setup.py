from setuptools import setup, find_packages

setup(
    name="propleads-pro",
    version="0.1.0",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
)
```
לחץ **Commit changes** ✅

---

**צעד 3 — ערוך `requirements.txt`**

ב-GitHub ← מצא `requirements.txt` ← עיפרון ✏️

**בסוף הקובץ** הוסף שורה אחת:
```
setuptools
