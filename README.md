# 📦 Inventory Management System

A web-based Inventory Management System developed using Python Flask and PostgreSQL to simplify and manage inventory operations efficiently. The application provides a centralized platform for managing products, monitoring stock levels, tracking inventory movements, and generating reports.

## 🚀 Features

- **Dashboard:** View important inventory information and stock statistics.
- **Product Management:** Add, view, update, and manage products.
- **Stock Management:** Track stock IN and stock OUT transactions.
- **Low Stock Alerts:** Identify products that are running low on stock.
- **Reports:** Generate inventory-related reports.
- **User Authentication:** Secure login functionality.
- **Profile Management:** Manage user profile information.
- **Settings:** Access and manage application settings.

## 🛠️ Technologies Used

### Backend

- Python
- Flask
- PostgreSQL

### Frontend

- HTML5
- CSS3

### Tools

- Visual Studio Code
- Git & GitHub
- Render

## 📁 Project Structure

```text
Inventory Management System/
│
├── app.py
├── requirements.txt
├── .gitignore
│
├── static/
│   └── css/
│       ├── add_product.css
│       ├── dashboard.css
│       ├── login.css
│       ├── low_stock.css
│       ├── products.css
│       ├── reports.css
│       ├── stock.css
│       ├── profile.css
│       └── settings.css
│
└── templates/
    ├── add_product.html
    ├── dashboard.html
    ├── login.html
    ├── low_stock_alerts.html
    ├── products.html
    ├── reports.html
    ├── stock.html
    ├── profile.html
    └── settings.html
```

## ⚙️ Installation and Setup

### 1. Clone the Repository

```bash
git clone https://github.com/Mahima-patidar441/Inventory-Management-System.git
```

### 2. Navigate to Project Directory

```bash
cd Inventory-Management-System
```

### 3. Create a Virtual Environment

```bash
python -m venv venv
```

Activate it:

**Windows:**

```bash
venv\Scripts\activate
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure Database

Make sure PostgreSQL is installed and running.

Configure the required database connection environment variables in your `.env` file:

```env
DB_HOST=your_database_host
DB_NAME=your_database_name
DB_USER=your_database_user
DB_PASSWORD=your_database_password
```

Use your actual database credentials. Never upload your `.env` file to GitHub.

### 6. Run the Application

```bash
python app.py
```

Open your browser and visit:

```text
http://127.0.0.1:5000
```

## 🌐 Deployment

The application is deployed using Render.

The deployment is connected to the GitHub repository, allowing updated code to be deployed through GitHub pushes.

## 🔒 Security

- Database credentials should be stored in environment variables.
- Never commit `.env` files.
- Keep sensitive configuration information private.

## 👨‍💻 Project Information

**Project Name:** Inventory Management System

**Backend:** Python Flask

**Database:** PostgreSQL

**Deployment Platform:** Render

---

Made with ❤️ using Python, Flask, PostgreSQL, HTML and CSS.
