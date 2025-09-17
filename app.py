from flask import Flask, render_template, request, redirect, url_for, flash, session
import mysql.connector
from flask_bcrypt import Bcrypt
import os
from datetime import datetime
from calendar import monthrange

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'a_very_secret_key')
bcrypt = Bcrypt(app)

db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '365Pass',
    'database': 'personal_finance_tracker'
}


def create_tables():
    connection = None
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()

        # Create the users table first, as other tables depend on it
        create_users_table_query = """
        CREATE TABLE IF NOT EXISTS users ( 
        id INT AUTO_INCREMENT PRIMARY KEY, 
        username VARCHAR(250) NOT NULL UNIQUE,
        password VARCHAR(250) NOT NULL
        )
        """
        cursor.execute(create_users_table_query)
        print("✅ Users table ensured to exist.")

        # Create the categories table, which depends on the users table
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
        print("✅ Categories table ensured to exist.")

        # Create the transactions table
        create_transactions_table_query = """
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            type ENUM('income','expense') NOT NULL,
            category_id INT,
            description VARCHAR(300) NOT NULL,
            transaction_date DATE NOT NULL,
            createdAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            modifiedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (category_id) REFERENCES categories(category_id)
        );
        """
        cursor.execute(create_transactions_table_query)
        print("✅ Transactions table ensured to exist.")

        # Create the budgets table
        create_budgets_table_query = """
        CREATE TABLE IF NOT EXISTS budgets (
            budget_id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            category_id INT NOT NULL,
            amount DECIMAL(10, 2) NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            createdAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            modifiedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (category_id) REFERENCES categories(category_id)
        );
        """
        cursor.execute(create_budgets_table_query)
        print("✅ Budgets table ensured to exist.")

        connection.commit()
        print("✅ All tables created successfully.")
    except mysql.connector.Error as err:
        print(f"⚠️ Error creating tables: {err}")
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
    categories = []
    total_income = 0
    total_expenses = 0
    budgets = []
    spent_per_category = {}

    search_query = request.args.get('q', '')

    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)
        query = "SELECT username FROM users WHERE id = %s"
        cursor.execute(query, (session['user_id'],))
        user = cursor.fetchone()
        username = user['username'] if user else 'Guest'

        query_categories = "SELECT category_id, name FROM categories WHERE user_id = %s"
        cursor.execute(query_categories, (session['user_id'],))
        categories = cursor.fetchall()

        base_query_transactions = """
        SELECT 
            t.*, c.name AS category_name
        FROM 
            transactions t
        LEFT JOIN 
            categories c ON t.category_id = c.category_id
        WHERE 
            t.user_id = %s
        """
        params = [session['user_id']]

        if search_query:
            base_query_transactions += """
            AND (t.description LIKE %s OR c.name LIKE %s)
            """
            search_pattern = f"%{search_query}%"
            params.append(search_pattern)
            params.append(search_pattern)

        base_query_transactions += " ORDER BY t.transaction_date DESC;"

        cursor.execute(base_query_transactions, tuple(params))
        transactions = cursor.fetchall()

        # --- CHANGES START HERE ---
        # Calculate spending per category
        for transaction in transactions:
            if transaction['type'] == 'expense' and transaction['category_name']:
                category_name = transaction['category_name']
                amount = float(transaction['amount'])
                spent_per_category[category_name] = spent_per_category.get(category_name, 0) + amount
        # --- CHANGES END HERE ---

        # Total income
        query_income = "SELECT SUM(amount) AS total FROM transactions WHERE user_id = %s AND type = 'income'"
        cursor.execute(query_income, (session['user_id'],))
        total_income = cursor.fetchone()['total'] or 0

        #  Total expenses
        query_expenses = "SELECT SUM(amount) AS total FROM transactions WHERE user_id = %s AND type = 'expense'"
        cursor.execute(query_expenses, (session['user_id'],))
        total_expenses = cursor.fetchone()['total'] or 0

        # Get budgets
        query_budgets = """
        SELECT b.*, c.name AS category_name
        FROM budgets b
        JOIN categories c ON b.category_id = c.category_id
        WHERE b.user_id = %s
        """
        cursor.execute(query_budgets, (session['user_id'],))
        budgets = cursor.fetchall()


    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        username = 'Guest'
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

    total_balance = total_income - total_expenses

    return render_template('dashboard.html',
                           username=username,
                           transactions=transactions,
                           categories=categories,
                           total_income=total_income,
                           total_expenses=total_expenses,
                           total_balance=total_balance,
                           search_query=search_query,
                           budgets=budgets,
                           spent_per_category=spent_per_category)


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
        category_id_str = request.form['category_id']

        # Convert empty string to None for database NULL
        category_id = int(category_id_str) if category_id_str else None

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

        cursor.execute(query, (user_id, amount, transaction_type, category_id, description, transaction_date))
        connection.commit()

        print("Transaction added successfully!")
        flash("Transaction added successfully!", "success")
    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        flash("Failed to add transaction.", "danger")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

    return redirect(url_for('dashboard'))


@app.route('/edit_transaction/<int:transaction_id>', methods=['GET'])
def edit_transaction(transaction_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    connection = None
    transaction = None
    categories = []

    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)

        # Get the transaction to be edited
        query_transaction = """
        SELECT *
        FROM transactions
        WHERE transaction_id = %s AND user_id = %s
        """
        cursor.execute(query_transaction, (transaction_id, session['user_id']))
        transaction = cursor.fetchone()

        if not transaction:
            flash("Transaction not found or you don't have permission to edit it.", "danger")
            return redirect(url_for('dashboard'))

        # Get all categories for the dropdown
        query_categories = "SELECT category_id, name FROM categories WHERE user_id = %s"
        cursor.execute(query_categories, (session['user_id'],))
        categories = cursor.fetchall()

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        flash("Failed to retrieve transaction details.", "danger")
        return redirect(url_for('dashboard'))
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

    return render_template('edit.html', transaction=transaction, categories=categories)


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
        category_id_str = request.form['category_id']

        # Convert empty string to None for database NULL
        category_id = int(category_id_str) if category_id_str else None

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
        SET amount = %s, type = %s, category_id = %s, description = %s, transaction_date = %s
        WHERE transaction_id = %s AND user_id = %s
        """
        cursor.execute(query,
                       (amount, transaction_type, category_id, description, transaction_date, transaction_id, user_id))
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


@app.route('/categories')
def categories():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    connection = None
    categories = []

    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)
        query = "SELECT * FROM categories WHERE user_id = %s"
        cursor.execute(query, (user_id,))
        categories = cursor.fetchall()

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        flash("Failed to retrieve categories.", "danger")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
    return render_template('categories.html', categories=categories)


@app.route('/add_category', methods=['POST'])
def add_category():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    category_name = request.form.get('category_name')

    if not category_name:
        flash("Category name cannot be empty.", "danger")
        return redirect(url_for('categories'))

    connection = None
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()
        query = "INSERT INTO categories (name, user_id, createdBy) VALUES (%s, %s, %s)"
        cursor.execute(query, (category_name, user_id, user_id))
        connection.commit()
        flash("Category added successfully!", "success")
    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        flash("Failed to add category.", "danger")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

    return redirect(url_for('categories'))


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


@app.route('/set_budget', methods=['POST'])
def set_budget():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']

    connection = None
    try:
        category_id = int(request.form['category_id'])
        # The database column is 'amount', not 'budget_amount'
        amount = float(request.form['budget_amount'])
        start_date_str = request.form['budget_start_date']
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()

        # Calculate the end date as the last day of the month
        _, last_day = monthrange(start_date.year, start_date.month)
        end_date = start_date.replace(day=last_day)

        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()

        # Check for existing budget for the same user, category, and month
        query_check = """
        SELECT COUNT(*) FROM budgets
        WHERE user_id = %s AND category_id = %s AND start_date = %s
        """
        cursor.execute(query_check, (user_id, category_id, start_date))
        if cursor.fetchone()[0] > 0:
            flash('Budget for this category and month already exists. Please edit it instead.', 'danger')
        else:
            query = """
            INSERT INTO budgets (user_id, category_id, amount, start_date, end_date)
            VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(query, (user_id, category_id, amount, start_date, end_date))
            connection.commit()
            flash('Budget set successfully!', 'success')

    except (KeyError, ValueError, mysql.connector.Error) as err:
        print(f"Database error or invalid form data: {err}")
        flash("Failed to set budget. Please check your data.", "danger")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

    return redirect(url_for('dashboard'))


@app.route('/edit_budget/<int:budget_id>', methods=['GET', 'POST'])
def edit_budget(budget_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    connection = None
    budget = None
    categories = []

    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)

        # Retrieve the budget to be edited
        query_budget = """
        SELECT *
        FROM budgets
        WHERE budget_id = %s AND user_id = %s
        """
        cursor.execute(query_budget, (budget_id, session['user_id']))
        budget = cursor.fetchone()

        if not budget:
            flash("Budget not found or you don't have permission to edit it.", "danger")
            return redirect(url_for('dashboard'))

        # Get all categories for the dropdown
        query_categories = "SELECT category_id, name FROM categories WHERE user_id = %s"
        cursor.execute(query_categories, (session['user_id'],))
        categories = cursor.fetchall()

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        flash("Failed to retrieve budget details for editing.", "danger")
        return redirect(url_for('dashboard'))
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

    return render_template('edit_budget.html', budget=budget, categories=categories)


@app.route('/update_budget/<int:budget_id>', methods=['POST'])
def update_budget(budget_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    connection = None

    try:
        amount = float(request.form['amount'])
        start_date = request.form['start_date']
        end_date = request.form['end_date']

        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()

        query = """
        UPDATE budgets
        SET amount = %s, start_date = %s, end_date = %s
        WHERE budget_id = %s AND user_id = %s
        """
        cursor.execute(query, (amount, start_date, end_date, budget_id, user_id))
        connection.commit()

        if cursor.rowcount == 0:
            flash("Failed to update budget. It may not exist or you lack permission.", "danger")
        else:
            flash("Budget updated successfully!", "success")

    except (KeyError, ValueError, mysql.connector.Error) as err:
        print(f"Error updating budget: {err}")
        flash("Failed to update budget. Please check your data.", "danger")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

    return redirect(url_for('dashboard'))


@app.route('/delete_budget/<int:budget_id>')
def delete_budget(budget_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']

    connection = None
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()
        query = "DELETE FROM budgets WHERE budget_id = %s AND user_id = %s"
        cursor.execute(query, (budget_id, user_id))
        connection.commit()
        if cursor.rowcount > 0:
            flash("Budget deleted successfully!", "success")
        else:
            flash("Budget not found or you don't have permission to delete it.", "danger")
    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        flash("Failed to delete budget.", "danger")
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
    create_tables()
    app.run(debug=True)
