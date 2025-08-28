from flask import Flask, render_template, request, redirect, url_for
import mysql.connector
from flask_bcrypt import Bcrypt

app = Flask(__name__)

app.secret_key = 'your_secret_key'
bcrypt = Bcrypt(app)

db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'thisdbpassword',
    'database': 'personal_finance_tracker'
}


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        connection = None
        try:
            connection = mysql.connector.connect(**db_config)
            cursor = connection.cursor()

            print(f"Login attempt with Username: {username} and Password: {password}")
            return redirect(url_for('dashboard'))

        except mysql.connector.Error as err:
            print(f"Database error: {err}")
            return "Database connection error."
        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()

        return "You have logged in successfully!"

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        connection = None
        try:
            connection = mysql.connector.connect(**db_config)
            cursor = connection.cursor()

            print(f"Registration attempt for Username: {username} and Password: {password}")

        except mysql.connector.Error as err:
            print(f"Database error: {err}")
            return "Database connection error."
        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()

        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')
@app.route('/')
def index():
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)
