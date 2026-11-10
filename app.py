from flask import Flask, render_template, request, redirect, url_for, session
import psycopg2
from werkzeug.security import generate_password_hash, check_password_hash
import os
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    return conn

app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY")


@app.route('/')
def home():

    registered = request.args.get('registered')

    return render_template(
        'login.html',
        registered=registered
    )

# Check Login

@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        username = request.form['username'].strip()
        password = request.form['password']

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT user_id, full_name, username, password
            FROM users
            WHERE username = %s
        """, (username,))

        user = cur.fetchone()

        cur.close()
        conn.close()

        if user and check_password_hash(user[3], password):

            session.clear()
            session['user_id'] = user[0]
            session['admin'] = user[2]
            session['full_name'] = user[1]

            return redirect(url_for('dashboard'))

        return render_template(
            'login.html',
            error="Incorrect username or password"
        )

    return redirect(url_for('home'))


# signup
@app.route('/signup', methods=['GET', 'POST'])
def signup():

    if request.method == 'POST':

        full_name = request.form['full_name'].strip()
        email = request.form['email'].strip().lower()
        username = request.form['username'].strip()
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if not all([full_name, email, username, password, confirm_password]):
            return render_template(
                'signup.html',
                error="Please fill all the fields."
            )

        if password != confirm_password:
            return render_template(
                'signup.html',
                error="Passwords do not match."
            )

        if len(password) < 8:
            return render_template(
                'signup.html',
                error="Password must be at least 8 characters."
            )

        conn = get_db_connection()
        cur = conn.cursor()

        try:
            cur.execute("""
                INSERT INTO users
                (full_name, email, username, password)
                VALUES (%s, %s, %s, %s)
            """, (
                full_name,
                email,
                username,
                generate_password_hash(password)
            ))

            conn.commit()

            return redirect(url_for('home', registered=1))

        except psycopg2.errors.UniqueViolation:
            conn.rollback()

            return render_template(
                'signup.html',
                error="Username or email already exists."
            )

        finally:
            cur.close()
            conn.close()

    return render_template('signup.html')


# Dashboard
@app.route("/dashboard")
def dashboard():

    if "admin" not in session:
        return redirect(url_for("login"))

    return render_template("dashboard.html")


# Products
@app.route('/products')
def products():

    if 'admin' not in session:
        return redirect(url_for('home'))

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM products ORDER BY product_id DESC")
    products = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('products.html', products=products)


# Add Product

@app.route('/add-product', methods=['GET', 'POST'])
def add_product():

    if 'admin' not in session:
        return redirect(url_for('home'))

    if request.method == 'POST':

        product_name = request.form['product_name']
        category = request.form['category']
        price = request.form['price']
        quantity = request.form['quantity']
        min_stock = request.form['min_stock']
        description = request.form['description']

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO products
            (product_name, category, price, quantity, min_stock, description)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            product_name,
            category,
            price,
            quantity,
            min_stock,
            description
        ))

        conn.commit()

        cur.close()
        conn.close()

        return redirect(url_for('products'))

    return render_template('add_product.html')



# Stock Management

@app.route('/stock-management', methods=['GET', 'POST'])
def stock_management():

    if 'admin' not in session:
        return redirect(url_for('home'))

    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':

        product_id = request.form['product_id']
        transaction_type = request.form['transaction_type']
        quantity = int(request.form['quantity'])
        notes = request.form['notes']

        if quantity <= 0:
            conn.close()
            return "Quantity must be greater than zero."

        try:
            cur.execute(
                "SELECT quantity FROM products WHERE product_id = %s FOR UPDATE",
                (product_id,)
            )
            product = cur.fetchone()

            if product is None:
                conn.rollback()
                return "Product not found."

            current_quantity = product[0]

            if transaction_type == 'OUT' and quantity > current_quantity:
                conn.rollback()
                return "Not enough stock available."

            if transaction_type == 'IN':
                new_quantity = current_quantity + quantity
            else:
                new_quantity = current_quantity - quantity

            cur.execute("""
                UPDATE products
                SET quantity = %s
                WHERE product_id = %s
            """, (new_quantity, product_id))

            cur.execute("""
                INSERT INTO stock_transactions
                (product_id, transaction_type, quantity, notes)
                VALUES (%s, %s, %s, %s)
            """, (product_id, transaction_type, quantity, notes))

            conn.commit()

        except Exception as e:
            conn.rollback()
            print("Stock Error:", e)
            return "Something went wrong while updating stock."

        finally:
            cur.close()
            conn.close()

        return redirect(url_for('stock_management'))

    cur.execute("""
        SELECT product_id, product_name, quantity
        FROM products
        ORDER BY product_name
    """)
    products = cur.fetchall()

    cur.execute("""
        SELECT st.transaction_id, p.product_name,
               st.transaction_type, st.quantity,
               st.transaction_date, st.notes
        FROM stock_transactions st
        JOIN products p ON st.product_id = p.product_id
        ORDER BY st.transaction_date DESC
    """)
    transactions = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        'stock.html',
        products=products,
        transactions=transactions
    )


# Low Stock Alerts

@app.route('/low-stock-alerts')
def low_stock_alerts():

    if 'admin' not in session:
        return redirect(url_for('home'))

    conn = get_db_connection()
    cur = conn.cursor()

    # Products whose quantity is at or below minimum stock
    cur.execute("""
        SELECT product_id, product_name, category,
               quantity, min_stock, price
        FROM products
        WHERE quantity <= COALESCE(min_stock, 5)
        ORDER BY quantity ASC
    """)

    low_stock_products = cur.fetchall()

    # Total low stock products
    total_low_stock = len(low_stock_products)

    # Products with zero quantity
    out_of_stock = sum(
        1 for product in low_stock_products if product[3] == 0
    )

    cur.close()
    conn.close()

    return render_template(
        'low_stock_alerts.html',
        products=low_stock_products,
        total_low_stock=total_low_stock,
        out_of_stock=out_of_stock
    )



# Reports


@app.route('/reports')
def reports():

    if 'admin' not in session:
        return redirect(url_for('home'))

    conn = get_db_connection()
    cur = conn.cursor()

    # 1. Overall inventory summary
    cur.execute("""
        SELECT
            COUNT(*),
            COALESCE(SUM(quantity), 0),
            COALESCE(SUM(price * quantity), 0),
            COUNT(*) FILTER (WHERE quantity = 0),
            COUNT(*) FILTER (
                WHERE quantity > 0
                AND quantity <= COALESCE(min_stock, 5)
            )
        FROM products
    """)

    summary = cur.fetchone()

    # 2. Category-wise stock
    cur.execute("""
        SELECT
            category,
            COUNT(*),
            COALESCE(SUM(quantity), 0),
            COALESCE(SUM(price * quantity), 0)
        FROM products
        GROUP BY category
        ORDER BY category
    """)

    category_report = cur.fetchall()

    # Data for category chart
    category_labels = [row[0] for row in category_report]
    category_values = [int(row[2]) for row in category_report]

    # 3. Total Stock In and Stock Out
    cur.execute("""
        SELECT
            COALESCE(SUM(quantity) FILTER (
                WHERE UPPER(transaction_type) = 'IN'
            ), 0),

            COALESCE(SUM(quantity) FILTER (
                WHERE UPPER(transaction_type) = 'OUT'
            ), 0)

        FROM stock_transactions
    """)

    stock_summary = cur.fetchone()

    stock_in = int(stock_summary[0])
    stock_out = int(stock_summary[1])

    # 4. Recent stock transactions
    cur.execute("""
        SELECT
            st.transaction_id,
            p.product_name,
            st.transaction_type,
            st.quantity,
            st.transaction_date
        FROM stock_transactions st
        JOIN products p
        ON st.product_id = p.product_id
        ORDER BY st.transaction_date DESC
        LIMIT 10
    """)

    recent_transactions = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
    'reports.html',
    summary=summary,
    category_report=category_report,
    category_labels=category_labels,
    category_values=category_values,
    stock_in=stock_in,
    stock_out=stock_out,
    stock_summary=stock_summary,
    recent_transactions=recent_transactions
)

    


# Logout
@app.route("/logout")
def logout():

    session.pop("admin", None)

    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=False)
