"""
Скрипт для создания релиза - упаковка EXE в ZIP
"""
import os
import shutil
import zipfile
from pathlib import Path
from datetime import datetime

print("=" * 70)
print("Создание релиза TransGoogleTest".center(70))
print("=" * 70)

# Проверка что dist существует
dist_dir = Path('dist/TransGoogleTest')
if not dist_dir.exists():
    print("\n[ERROR] Папка dist/TransGoogleTest не найдена!")
    print("Сначала соберите EXE: python build_exe.py")
    exit(1)

exe_file = dist_dir / 'TransGoogleTest.exe'
if not exe_file.exists():
    print("\n[ERROR] TransGoogleTest.exe не найден!")
    print("Сначала соберите EXE: python build_exe.py")
    exit(1)

print(f"\n[OK] Найден EXE: {exe_file}")
print(f"[OK] Размер: {exe_file.stat().st_size / (1024*1024):.1f} MB")

# Создаем папку releases если её нет
releases_dir = Path('releases')
releases_dir.mkdir(exist_ok=True)

# Имя архива с версией и датой
version = "v1.0.0"  # Можно менять
date = datetime.now().strftime("%Y%m%d")
zip_name = f"TransGoogleTest-{version}-win64.zip"
zip_path = releases_dir / zip_name

print(f"\n[*] Создание архива: {zip_path}")

# Создаем ZIP архив
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
    # Добавляем все файлы из dist/TransGoogleTest
    for root, dirs, files in os.walk(dist_dir):
        for file in files:
            file_path = Path(root) / file
            # Путь в архиве (относительно dist)
            arcname = file_path.relative_to(dist_dir.parent)
            print(f"    Добавление: {arcname}")
            zipf.write(file_path, arcname)

zip_size = zip_path.stat().st_size / (1024*1024)

print("\n" + "=" * 70)
print("РЕЛИЗ СОЗДАН!".center(70))
print("=" * 70)
print(f"\n[+] Архив: {zip_path}")
print(f"[+] Размер: {zip_size:.1f} MB")
print(f"\n[>] Загрузите этот файл в GitHub Release")
print(f"[i] Пользователи скачают, распакуют и запустят TransGoogleTest.exe")

print("\n" + "=" * 70)
print("Следующие шаги:".center(70))
print("=" * 70)
print("""
1. Перейдите на GitHub: https://github.com/ваш-username/TransGoogleTest
2. Нажмите "Releases" → "Create a new release"
3. Tag version: v1.0.0
4. Release title: TransGoogleTest v1.0.0
5. Перетащите файл: releases/{zip_name}
6. Опишите изменения
7. Нажмите "Publish release"

Готово! Теперь пользователи могут скачать готовый EXE!
""".format(zip_name=zip_name))
