"""
Скрипт для сборки приложения в .exe файл
"""
import os
import sys
import shutil
from pathlib import Path

# Установка UTF-8 для Windows консоли
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

print("=" * 70)
print("Сборка TransGoogleTest в EXE".center(70))
print("=" * 70)

# Проверка что PyInstaller установлен
try:
    import PyInstaller
    print("[OK] PyInstaller установлен")
except ImportError:
    print("[ERROR] PyInstaller не установлен!")
    print("\nУстановите: pip install pyinstaller")
    sys.exit(1)

# Очистка старых сборок
print("\n[*] Очистка старых сборок...")
for folder in ['build', 'dist']:
    if Path(folder).exists():
        shutil.rmtree(folder)
        print(f"    Удалена папка: {folder}")

# Запуск PyInstaller
print("\n[*] Запуск PyInstaller...")
print("    Это может занять 2-5 минут...\n")

os.system('pyinstaller TransGoogleTest.spec')

# Проверка результата
exe_path = Path('dist/TransGoogleTest/TransGoogleTest.exe')
if exe_path.exists():
    size_mb = exe_path.stat().st_size / (1024 * 1024)
    print("\n" + "=" * 70)
    print("СБОРКА УСПЕШНА!".center(70))
    print("=" * 70)
    print(f"\n[+] EXE файл: {exe_path}")
    print(f"[+] Размер: {size_mb:.1f} MB")
    print(f"\n[>] Запуск: dist\\TransGoogleTest\\TransGoogleTest.exe")
    print("\n[i] Для создания установщика скопируйте всю папку dist\\TransGoogleTest")
else:
    print("\n[ERROR] Ошибка сборки!")
    print("Проверьте логи выше")
    sys.exit(1)
