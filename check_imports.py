import os
import re

# Паттерн для поиска опечатанных импортов
WRONG_IMPORT_PATTERN = re.compile(r"from\s+classes\.GlobalVarialbles\s+import\s+GlobalVariables")

project_root = os.path.dirname(os.path.abspath(__file__))
print(f"🔍 Проверяю импорты в проекте: {project_root}\n")

found = []

for root, _, files in os.walk(project_root):
    for f in files:
        if f.endswith(".py"):
            path = os.path.join(root, f)
            try:
                with open(path, "r", encoding="utf-8") as file:
                    content = file.read()
                    if WRONG_IMPORT_PATTERN.search(content):
                        found.append(path)
            except Exception as e:
                print(f"⚠️ Ошибка чтения {path}: {e}")

if found:
    print("❌ Найдены неправильные импорты:")
    for f in found:
        print("   →", f)
else:
    print("✅ Все импорты правильные (GlobalVariables).")
