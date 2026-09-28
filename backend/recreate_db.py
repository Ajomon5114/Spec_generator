import os
import sqlite3
import json
import bcrypt

def recreate_db():
    try:
        if os.path.exists('specifications.db'):
            os.remove('specifications.db')

        conn = sqlite3.connect('specifications.db')
        c = conn.cursor()
        c.execute('DROP TABLE IF EXISTS users')
        c.execute('DROP TABLE IF EXISTS sessions')
        c.execute('DROP TABLE IF EXISTS templates')
        c.execute('DROP TABLE IF EXISTS app_settings')

        c.execute('''CREATE TABLE users
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
                      password_hash TEXT NOT NULL, role TEXT NOT NULL)''')
                      
        c.execute('''CREATE TABLE sessions
                     (token TEXT PRIMARY KEY, user_id INTEGER NOT NULL,
                      expires_at TIMESTAMP NOT NULL,
                      FOREIGN KEY (user_id) REFERENCES users (id))''')
                      
        c.execute('''CREATE TABLE templates
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, product_name TEXT UNIQUE NOT NULL,
                      spec_data TEXT NOT NULL)''')
                      
        c.execute('''CREATE TABLE app_settings
                     (setting_key TEXT PRIMARY KEY, setting_value TEXT NOT NULL)''')

        # Add admin and user using raw bcrypt
        admin_hash = bcrypt.hashpw(b'admin', bcrypt.gensalt()).decode('utf-8')
        user_hash = bcrypt.hashpw(b'user', bcrypt.gensalt()).decode('utf-8')
        c.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)", ('admin', admin_hash, 'admin'))
        c.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)", ('user', user_hash, 'user'))

        # Insert default settings with Organoleptic at top
        default_protocols = [
            'Organoleptic', 'Internal method', 'Eur.Ph <2.2.32>', 'Eur.Ph <2.9.34>',
            'Eur.Ph <2.9.12>', 'EC <396/2005>', 'EC<2023/915>', 'Eur.Ph <2.8.18>',
            'EC<2023/951>', 'Eur.Ph <2.4.24>', 'Eur.Ph.<5.1.8>', 'Internal method by HPLC'
        ]
        c.execute("INSERT INTO app_settings (setting_key, setting_value) VALUES (?, ?)", 
                 ('protocols', json.dumps(default_protocols)))
        
        conn.commit()
        conn.close()
        print('DB recreated successfully!')
    except Exception as e:
        print('Error:', e)
        
recreate_db()
