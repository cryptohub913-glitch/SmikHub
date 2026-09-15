import sqlite3

def run_migration():
    # Подключаемся к локальной базе данных SQLite (обычно называется database.sqlite или app.db, проверь имя в корне)
    # Попробуем найти файл базы в папке или корне
    import glob
    db_files = glob.glob("*.db") + glob.glob("*.sqlite") + glob.glob("*.sqlite3") + glob.glob("smikhub/**/*.db", recursive=True)
    
    if not db_files:
        print("Файл базы данных (.db / .sqlite) не найден в корне проекта. Укажи путь вручную.")
        return

    db_path = db_files[0]
    print(f"Найден файл базы данных: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    columns_to_add = [
        "subgram_token VARCHAR",
        "flyer_token VARCHAR",
        "traffy_token VARCHAR",
        "piarflow_token VARCHAR",
        "tgrass_token VARCHAR"
    ]

    for col in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE bots ADD COLUMN {col};")
            print(f"Успешно добавлена колонка: {col}")
        except sqlite3.OperationalError as e:
            print(f"Пропущено (возможно, уже существует): {col} ({e})")

    conn.commit()
    conn.close()
    print("Миграция базы данных SQLite успешно завершена!")

if __name__ == "__main__":
    run_migration()