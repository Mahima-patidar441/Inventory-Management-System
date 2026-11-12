from flask import Flask, render_template, request, redirect, url_for, session , flash
import psycopg2
import os
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
from dotenv import load_dotenv

load_dotenv(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
    override=True
)

print("ENV FILE:", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
print("ENV EXISTS:", os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")))
print("DATABASE URL LOADED:", bool(os.getenv("DATABASE_URL")))

def get_inventory_summary():

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            COUNT(*),
            COALESCE(SUM(quantity), 0),
            COALESCE(SUM(price * quantity), 0),

            COUNT(*) FILTER (
                WHERE quantity > 0
                AND quantity <= COALESCE(min_stock, 5)
            ),

            COUNT(*) FILTER (
                WHERE quantity = 0
            )

        FROM products
    """)

    result = cur.fetchone()

    cur.close()
    conn.close()

    return {
        'total_products': result[0],
        'total_stock': result[1],
        'total_value': result[2],
        'low_stock': result[3],
        'out_of_stock': result[4]
    }

print("DATABASE HOST:", os.getenv("DATABASE_URL", "").split("@")[-1].split("/")[0])

def get_db_connection():
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    return conn

app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY")

app.secret_key = "inventory_admin_secret_key"

ADMIN_USERNAME = "admin123"
ADMIN_PASSWORD_HASH = generate_password_hash("123123123")


@app.route("/")
def home():
    return render_template("login.html")



@app.route("/login", methods=["POST"])
def check_login():

    username = request.form.get("username")
    password = request.form.get("password")

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

        session["admin"] = user[2]
        session["user_id"] = user[0]
        session["full_name"] = user[1]

        return redirect(url_for("dashboard"))

    else:
        return render_template(
            "login.html",
            error="Invalid username or password!"
        )


# Dashboard
@app.route('/dashboard')
def dashboard():

    if 'admin' not in session:
        return redirect(url_for('home'))

    conn = get_db_connection()
    cur = conn.cursor()

    # Summary cards
    cur.execute("""
        SELECT
            COUNT(*),
            COALESCE(SUM(quantity), 0),
            COALESCE(SUM(price * quantity), 0),
            COUNT(*) FILTER (
                WHERE quantity > 0
                AND quantity <= COALESCE(min_stock, 5)
            ),
            COUNT(*) FILTER (WHERE quantity = 0)
        FROM products
    """)

    result = cur.fetchone()

    summary = {
        'total_products': result[0],
        'total_stock': result[1],
        'total_value': result[2],
        'low_stock': result[3],
        'out_of_stock': result[4]
    }

    # Recent Stock Transactions
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
        ORDER BY st.transaction_date DESC,
                 st.transaction_id DESC
        LIMIT 6
    """)

    recent_transactions = cur.fetchall()

    # Low Stock Alerts
    cur.execute("""
        SELECT
            product_name,
            quantity,
            min_stock
        FROM products
        WHERE quantity <= COALESCE(min_stock, 5)
        ORDER BY quantity ASC
        LIMIT 6
    """)

    low_stock_products = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        'dashboard.html',
        summary=summary,
        recent_transactions=recent_transactions,
        low_stock_products=low_stock_products
    )

# Products

@app.route('/products')
def products():

    if 'admin' not in session:
        return redirect(url_for('home'))

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            product_id,
            product_name,
            category,
            price,
            quantity,
            min_stock
        FROM products
        ORDER BY product_id DESC
    """)

    products = cur.fetchall()

    cur.execute("""
        SELECT DISTINCT category
        FROM products
        WHERE category IS NOT NULL
        ORDER BY category
    """)

    categories = [row[0] for row in cur.fetchall()]

    cur.close()
    conn.close()

    return render_template(
        'products.html',
        products=products,
        categories=categories
    )


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

    cur.execute("""
        SELECT product_id, product_name, category,
               quantity, min_stock, price
        FROM products
        WHERE quantity > 0
        AND quantity <= COALESCE(min_stock, 5)
        ORDER BY quantity ASC
    """)

    low_stock_products = cur.fetchall()

    cur.execute("""
        SELECT product_id, product_name, category,
               quantity, min_stock, price
        FROM products
        WHERE quantity = 0
        ORDER BY product_id DESC
    """)

    out_of_stock_products = cur.fetchall()

    cur.close()
    conn.close()

    summary = get_inventory_summary()

    return render_template(
        'low_stock_alerts.html',
        products=low_stock_products,
        total_low_stock=summary['low_stock'],
        out_of_stock=summary['out_of_stock'],
        out_of_stock_products=out_of_stock_products,
        summary=summary
    )

# Reports



@app.route('/reports')
def reports():

    if 'admin' not in session:
        return redirect(url_for('home'))

    # Common inventory summary
    inventory = get_inventory_summary()

    # Keep the existing reports summary order:
    # 0 Total Products
    # 1 Total Stock
    # 2 Total Value
    # 3 Out of Stock
    # 4 Low Stock

    summary = (
        inventory['total_products'],
        inventory['total_stock'],
        inventory['total_value'],
        inventory['out_of_stock'],
        inventory['low_stock']
    )

    conn = get_db_connection()
    cur = conn.cursor()

    # Category-wise stock
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

    category_labels = [row[0] for row in category_report]
    category_values = [int(row[2]) for row in category_report]

    # Stock In and Stock Out
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

    # Recent transactions
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
        inventory=inventory,
        category_report=category_report,
        category_labels=category_labels,
        category_values=category_values,
        stock_in=stock_in,
        stock_out=stock_out,
        stock_summary=stock_summary,
        recent_transactions=recent_transactions
    )





@app.route('/settings', methods=['GET', 'POST'])
def settings():

    if 'admin' not in session:
        return redirect(url_for('home'))

    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':

        action = request.form.get('action')

        # Update Account Details
        if action == 'update_profile':

            full_name = request.form.get('full_name', '').strip()
            email = request.form.get('email', '').strip()
            username = request.form.get('username', '').strip()

            if not full_name or not email or not username:
                flash('Please fill all account details.', 'error')

            else:
                try:
                    cur.execute("""
                        UPDATE users
                        SET full_name = %s,
                            email = %s,
                            username = %s
                        WHERE user_id = %s
                    """, (
                        full_name,
                        email,
                        username,
                        session['user_id']
                    ))

                    conn.commit()

                    session['admin'] = username
                    session['full_name'] = full_name

                    flash('Account details updated successfully!', 'success')

                except Exception:
                    conn.rollback()
                    flash('Email or username may already be in use.', 'error')

        # Change Password
        elif action == 'change_password':

            current_password = request.form.get('current_password', '')
            new_password = request.form.get('new_password', '')
            confirm_password = request.form.get('confirm_password', '')

            cur.execute("""
                SELECT password FROM users
                WHERE user_id = %s
            """, (session['user_id'],))

            user = cur.fetchone()

            if not user or not check_password_hash(user[0], current_password):
                flash('Current password is incorrect.', 'error')

            elif len(new_password) < 6:
                flash('New password must contain at least 6 characters.', 'error')

            elif new_password != confirm_password:
                flash('New password and confirm password do not match.', 'error')

            else:
                hashed_password = generate_password_hash(new_password)

                cur.execute("""
                    UPDATE users
                    SET password = %s
                    WHERE user_id = %s
                """, (hashed_password, session['user_id']))

                conn.commit()

                flash('Password changed successfully!', 'success')

        # Save Appearance
        elif action == 'save_theme':

            theme = request.form.get('theme')

            if theme in ['light', 'dark']:

                cur.execute("""
                    UPDATE users
                    SET theme = %s
                    WHERE user_id = %s
                """, (theme, session['user_id']))

                conn.commit()

                flash('Appearance settings saved successfully!', 'success')

            else:
                flash('Please select a valid theme.', 'error')

        cur.close()
        conn.close()

        return redirect(url_for('settings'))

    # Fetch Account Details
    cur.execute("""
        SELECT full_name, email, username, theme
        FROM users
        WHERE user_id = %s
    """, (session['user_id'],))

    user = cur.fetchone()

    cur.close()
    conn.close()

    if user is None:
        return redirect(url_for('logout'))

    return render_template('settings.html', user=user)




@app.route('/my-profile')
def my_profile():

    if 'admin' not in session:
        return redirect(url_for('home'))

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT full_name, email, username, created_at
        FROM users
        WHERE user_id = %s
    """, (session['user_id'],))

    profile = cur.fetchone()

    cur.close()
    conn.close()

    if profile is None:
        return redirect(url_for('logout'))

    return render_template('profile.html', profile=profile)


# Logout
@app.route("/logout")
def logout():

    session.pop("admin", None)

    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=False)