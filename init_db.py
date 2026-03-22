"""Veritabanını sıfırdan oluşturur. Sadece bir kez çalıştır."""
from app import init_db
init_db()
print("Veritabanı oluşturuldu: platform.db")
