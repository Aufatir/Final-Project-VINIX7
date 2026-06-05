FROM python:3.9-slim

# Gunakan user non-root (syarat keamanan dari Hugging Face Spaces)
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

# Set working directory
WORKDIR /app

# Salin requirements dan instal pustaka
COPY --chown=user requirements.txt requirements.txt
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Salin seluruh isi proyek ke dalam Docker
COPY --chown=user . /app

# Berikan izin tulis (write permission) agar fitur Auto-Sync dataset bisa berjalan
RUN chmod 777 /app/rupiah_dataset_fixed_auto.csv

# Hugging Face Spaces secara default menggunakan port 7860
EXPOSE 7860

# Jalankan server Gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:7860", "web_app.app:app", "--timeout", "120"]
