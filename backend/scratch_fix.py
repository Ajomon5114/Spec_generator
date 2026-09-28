import sqlite3

def fix_db():
    try:
        with open('specifications.db', 'rb') as f:
            data = f.read()

        # The user accidentally added Organoleptic inside the JSON string
        bad_str = b'col":"Organoleptic", "Internal method"'
        good_str = b'col": "Internal method"'

        print("Bad string found:", data.count(bad_str))

        if data.count(bad_str) > 0:
            data = data.replace(bad_str, good_str)
            with open('specifications_fixed.db', 'wb') as f:
                f.write(data)
            print("Wrote fixed db.")
    except Exception as e:
        print("Error:", e)

fix_db()
