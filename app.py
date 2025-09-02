from flask import Flask, render_template, request, redirect, url_for, flash, session
import mysql.connector
from flask_bcrypt import Bcrypt
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'a_very_secret_key')
bcrypt = Bcrypt(app)

db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Pass',
    'database': 'personal_finance_tracker'
}

def create_users_table():
    connection = None
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()
        create_table_query = """
        CREATE TABLE IF NOT EXISTS users ( 
        id INT AUTO_INCREMENT PRIMARY KEY, 
        username VARCHAR(250) NOT NULL UNIQUE,
        password VARCHAR(250) NOT NULL
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

def create_finance_tables():
    connection = None
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()


        create_categories_table_query = """
        CREATE TABLE IF NOT EXISTS categories (
            category_id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(250) NOT NULL,
            user_id INT,
            createdBy INT NOT NULL,
            createdAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            modifiedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (createdBy) REFERENCES users(id)
        );
        """
        cursor.execute(create_categories_table_query)


        create_transactions_table_query = """
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            amount DECIMAL(10, 2) NOT NULL,
            type ENUM('income', 'expense') NOT NULL,
            category_id INT NULL,
            description VARCHAR(300) NOT NULL,
            transaction_date DATE NOT NULL,
            createdAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            modifiedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (category_id) REFERENCES categories(category_id)
        );
        """
        cursor.execute(create_transactions_table_query)

        connection.commit()
        print("✅ Categories and transactions tables created successfully.")

    except mysql.connector.Error as err:
        print(f"⚠️ Error creating finance tables: {err}")

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
    transactions = []
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)
        query = "SELECT username FROM users WHERE id = %s"
        cursor.execute(query, (session['user_id'],))
        user = cursor.fetchone()
        username = user['username'] if user else 'Guest'
        query_transactions = "SELECT * FROM transactions WHERE user_id = %s ORDER BY transaction_date DESC"
        cursor.execute(query_transactions, (session['user_id'],))
        transactions = cursor.fetchall()
    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        username = 'Guest'
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
    return render_template('dashboard.html', username=username, transactions=transactions)

@app.route('/add_transaction', methods=['POST'])
def add_transaction():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    try:
        amount = float(request.form['amount'])
        transaction_type = request.form['type']
        description = request.form['description']
        transaction_date = request.form['transaction_date']
        if not description or not transaction_date:
            raise ValueError("All fields must be filled.")
    except (KeyError, ValueError) as e:
        print(f"Form data error: {e}")
        flash("Invalid form data. Please fill all fields correctly.", "danger")
        return redirect(url_for('dashboard'))
    connection = None
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()
        query = """
        INSERT INTO transactions (user_id, amount, type, category_id, description, transaction_date)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (user_id, amount, transaction_type, None, description, transaction_date))
        connection.commit()
        flash("Transaction added successfully!", "success")
    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        flash("Failed to add transaction.", "danger")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
    return redirect(url_for('dashboard'))

@app.route('/delete_transaction/<int:transaction_id>')
def delete_transaction(transaction_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    connection = None
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()
        query = "DELETE FROM transactions WHERE transaction_id = %s AND user_id = %s"
        cursor.execute(query, (transaction_id, user_id))
        connection.commit()
        flash("Transaction deleted successfully!", "success")
    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        flash("Failed to delete transaction.", "danger")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
    return redirect(url_for('dashboard'))


@app.route('/edit_transaction/<int:transaction_id>')
def edit_transaction(transaction_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    connection = None
    transaction = None
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)
        query = "SELECT * FROM transactions WHERE transaction_id = %s AND user_id = %s"
        cursor.execute(query, (transaction_id, session['user_id']))
        transaction = cursor.fetchone()

        if not transaction:
            flash("Transaction not found or you don't have permission to edit it.", "danger")
            return redirect(url_for('dashboard'))

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        flash("Failed to retrieve transaction for editing.", "danger")
        return redirect(url_for('dashboard'))
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

    return render_template('edit.html', transaction=transaction)


@app.route('/update_transaction/<int:transaction_id>', methods=['POST'])
def update_transaction(transaction_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    try:
        amount = float(request.form['amount'])
        transaction_type = request.form['type']
        description = request.form['description']
        transaction_date = request.form['transaction_date']

        if not description or not transaction_date:
            raise ValueError("All fields must be filled.")

    except (KeyError, ValueError) as e:
        print(f"Form data error: {e}")
        flash("Invalid form data. Please fill all fields correctly.", "danger")
        return redirect(url_for('edit_transaction', transaction_id=transaction_id))

    connection = None
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()

        query = """
                UPDATE transactions
                SET amount = %s,type = %s,description= %s,transaction_date = %s
                WHERE transaction_id = %s AND user_id = %s \
                """
        cursor.execute(query, (amount, transaction_type, description, transaction_date, transaction_id, user_id))
        connection.commit()

        if cursor.rowcount == 0:
            flash("Failed to update transaction. It may not exist or you lack permission.", "danger")
        else:
            flash("Transaction updated successfully!", "success")

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        flash("Failed to update transaction.", "danger")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

    return redirect(url_for('dashboard'))


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route('/')
def index():
    return redirect(url_for('login'))

if __name__ == '__main__':
    create_users_table()
    create_finance_tables()
    app.run(debug=True)
