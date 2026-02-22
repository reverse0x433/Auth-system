# Auth System

A full authentication system built with Flask and PostgreSQL. Project 1 of 6 in a Python + Flask + PostgreSQL learning series.

## Features

- User registration with email validation
- Login / logout with session management
- Remember me (persistent session for 30 days)
- Forgot password with email reset link
- Password reset with token expiry (1 hour)
- IP-based rate limiting on login (5 attempts per 5 minutes, rolling window)
- Timing attack protection — dummy bcrypt check runs even when email is not found
- Password reset tokens hashed with bcrypt before storage (raw token only in email)
- Prevents reuse of old password on reset

## Tech Stack

- **Flask** — web framework
- **PostgreSQL** — database
- **psycopg2** — PostgreSQL driver
- **bcrypt** — password hashing
- **Flask-Mail** — email sending
- **python-dotenv** — environment variable loading
- **email-validator** — email format validation

## Project Structure

```
auth_system/
├── app.py            # All routes and logic
├── model.sql         # Database schema
├── requirements.txt  # Python dependencies
├── .env              # Environment variables (not committed)
├── .env.example      # Template for .env
├── .gitignore
└── templates/
    ├── base.html
    ├── login.html
    ├── register.html
    ├── dashboard.html
    ├── forgot_password.html
    └── reset_password.html
```

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Create the database
```bash
psql -U postgres -h 127.0.0.1 -c "CREATE DATABASE auth_db;"
```

### 3. Run the schema
Connect to psql and paste the contents of `model.sql`, or:
```bash
psql -U postgres -h 127.0.0.1 -d auth_db -f model.sql
```

### 4. Configure environment variables
Copy `.env.example` to `.env` and fill in your values:
```
SECRET_KEY=your_random_secret_key
DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/auth_db
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_gmail_app_password
```

> For Gmail, use an App Password (Google Account → Security → App Passwords), not your regular password.

### 5. Run the app
```bash
python app.py
```

Visit `http://localhost:5000/register` in your browser.

## Database Schema

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL
);

CREATE INDEX idx_user_username ON users(username);
CREATE INDEX idx_user_email ON users(email);
CREATE INDEX idx_tokens_expiry ON tokens(expires_at);
```

> Reset tokens are hashed with bcrypt before being stored — the raw token only ever exists in the email link.

## Routes

| Method | Route | Description |
|--------|-------|-------------|
| GET/POST | `/register` | Register a new account |
| GET/POST | `/login` | Login |
| GET | `/logout` | Logout |
| GET/POST | `/forgot-password` | Request password reset email |
| GET/POST | `/reset-password/<token>` | Reset password via token |
| GET | `/` | Dashboard (protected) |
