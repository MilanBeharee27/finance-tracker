from flask import Flask, render_template, request, redirect, url_for, flash, session
import mysql.connector
from flask_bcrypt import Bcrypt

app = Flask(__name__)
app.secret_key = 'your_secret_key'
bcrypt = Bcrypt(app)

db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '3',
    'database': 'personal_finance_tracker'
}


def create_users_table():
    connection = None
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()

        create_table_query = """
        CREATE TABLE IF NOT EXISTS users ( 
        id INT  AUTO_INCREMENT PRIMARY KEY, 
        username VARCHAR ( 250 ) NOT NULL UNIQUE,
         password VARCHAR (250) NOT NULL UNIQUE,
        )
        """
        cursor.execute(create_table_query)
        connection.commit()
        print("Users table created successfully.")
    except mysql.connector.Error as err:
        print(f"Error creating table: {err}")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        connection = None
        try:
            connection = mysql.connector.connect(**db_config)
            cursor = connection.cursor(dictionary=True)

            query = "SELECT * FROM users WHERE username = %s"
            cursor.execute(query, (username,))
            user = cursor.fetchone()

            if user and bcrypt.check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                print(f"Login successful for user: {username}")
                flash("Login successful!", "success")
                return redirect(url_for('dashboard'))
            else:
                print(f"Login failed for user: {username}")
                flash("Invalid username or password.", "danger")
                return redirect(url_for('login'))

        except mysql.connector.Error as err:
            print(f"Database error: {err}")
            flash("Database connection error.", "danger")
            return redirect(url_for('login'))
        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        connection = None
        try:
            connection = mysql.connector.connect(**db_config)
            cursor = connection.cursor()

            query = "INSERT INTO users (username, password) VALUES (%s, %s)"
            cursor.execute(query, (username, hashed_password))
            connection.commit()

            print(f"Registration successful for user: {username}")
            flash("You have successfully registered! Please log in.", "success")

        except mysql.connector.Error as err:
            if err.errno == mysql.connector.errorcode.ER_DUP_ENTRY:
                print(f"Registration failed: username '{username}' already exists.")
                flash("Username already exists. Please choose a different one.", "danger")
            else:
                print(f"Database error: {err}")
                flash("Database connection error.", "danger")
            return redirect(url_for('register'))
        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()

        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    connection = None
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)

        query = "SELECT username FROM users WHERE id = %s"
        cursor.execute(query, (session['user_id'],))
        user = cursor.fetchone()

        username = user['username'] if user else 'Guest'

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        username = 'Guest'
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

    return render_template('dashboard.html', username=username)


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))


@app.route('/')
def index():
    return redirect(url_for('login'))


if __name__ == '__main__':
    create_users_table()
    app.run(debug=True)
