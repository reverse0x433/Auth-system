import psycopg2,bcrypt,os,secrets,time
from collections import defaultdict
from dotenv import load_dotenv
from datetime import timedelta,datetime
from email_validator import validate_email,EmailNotValidError
from flask import Flask,redirect,render_template,session,request
from flask_mail import Mail,Message

load_dotenv()

failed_attempts = defaultdict(list)
RATE_LIMIT = 5
BLOCK_TIME = 300

app = Flask(__name__)
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT'))
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')

app.permanent_session_lifetime = timedelta(days=30)
mail = Mail(app)
app.secret_key = os.getenv("SECRET_KEY")

@app.route('/')
def dashboard():
    if "user_id" not in session:
        return redirect("/login")
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = %s",(session["user_id"],))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("dashboard.html", username=rows[0][1], email=rows[0][2])

@app.route('/login', methods=["GET","POST"])
def login():
 
    if request.method == "POST":
        email = request.form.get('email')
        password = request.form.get('password')
        if not email:
            return render_template("login.html", error="Invalid email")
        elif not password:
            return render_template("login.html", error="Invalid password")
        
        try:
            validate_email(email)
        except EmailNotValidError:
            return render_template("login.html", error="Invalid email")
        
        ip = request.remote_addr
        now = time.time()
        failed_attempts[ip] = [t for t in failed_attempts[ip] if now - t < BLOCK_TIME]
        if len(failed_attempts[ip]) >= RATE_LIMIT:
            return render_template("login.html", error="Too many attempts. Try again in 5 minutes.")

        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email = %s",(email,))
        rows = cur.fetchall()

        dummy_hash = bcrypt.hashpw(b'dummy', bcrypt.gensalt()).decode('utf-8')

        if len(rows)!=1:
            bcrypt.checkpw(password.encode('utf-8'),dummy_hash.encode('utf-8'))
            failed_attempts[ip].append(now)
            cur.close()
            conn.close()
            return render_template("login.html",error="Invalid credentials")
        
        if not bcrypt.checkpw(password.encode('utf-8'), rows[0][3].encode('utf-8')):
            failed_attempts[ip].append(now)
            cur.close()
            conn.close()
            return render_template("login.html",error="Invalid credentials")
        
        if ip in failed_attempts:
            del failed_attempts[ip]

        session["user_id"] = rows[0][0]
        session.permanent = True if request.form.get("remember_me") else False

        cur.close()
        conn.close()
        return redirect("/")

    return render_template("login.html")

@app.route('/logout')
def logout():
    session.clear()
    return redirect("/login")

@app.route('/register', methods=["GET","POST"])
def register():
    if request.method == "POST":
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        if not username:
            return render_template("register.html", error="Invalid username")
        elif not email:
            return render_template("register.html", error="Invalid email")
        elif not password:
            return render_template("register.html", error="Invalid password")
        
        try:
            validate_email(email)
        except EmailNotValidError:
            return render_template("register.html", error="Invalid email")
        
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        cur = conn.cursor()

        password_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt).decode('utf-8')

        try:
            cur.execute("INSERT INTO users(email, username, password_hash) VALUES(%s, %s, %s) RETURNING id",(email, username, hashed))
            rows = cur.fetchone()
            session["user_id"] = rows[0]
            conn.commit()
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            return render_template("register.html", error="Email or username already exists")
        finally:
            cur.close()
            conn.close() 
        return redirect("/")
    return render_template("register.html")

@app.route('/reset-password/<token>', methods=["GET","POST"])
def reset_password(token):
    if request.method == "POST":
        password = request.form.get("password")
        confirmation = request.form.get("confirm_password")
        if not password or not confirmation:
            return render_template("reset_password.html", error="Invalid password",token=token)
        elif password != confirmation:
            return render_template("reset_password.html", error="passwords do not match",token=token)
        
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        cur = conn.cursor()
        try:
            cur.execute("SELECT user_id,token_hash FROM tokens WHERE expires_at > NOW() AT TIME ZONE 'UTC'")
            token_rows = cur.fetchall()
            user_id = None

            for token_row in token_rows:
                try:
                    if bcrypt.checkpw(token.encode('utf-8'),token_row[1].encode('utf-8')):
                        user_id = token_row[0]
                        break
                except Exception:
                    continue
            if not user_id:
                return render_template("reset_password.html",error="Invalid or expired token",token=token)

            cur.execute("SELECT * FROM users WHERE id = %s",(user_id,))
            rows = cur.fetchall()

            if bcrypt.checkpw(password.encode('utf-8'),rows[0][3].encode('utf-8')):
                return render_template("reset_password.html",error="You cant enter old password",token=token)

            salt = bcrypt.gensalt()
            hashed = bcrypt.hashpw(password.encode('utf-8'),salt).decode('utf-8')
            cur.execute("UPDATE users SET password_hash = %s WHERE id = %s",(hashed,rows[0][0]))
            cur.execute("DELETE FROM tokens WHERE user_id = %s",(rows[0][0],))
            conn.commit()
            return redirect("/login")
        finally:
            cur.close()
            conn.close()

    return render_template("reset_password.html",token=token)

@app.route('/forgot-password',methods=["GET","POST"])
def forgot_password():
    if request.method == "POST":
        if not request.form.get("email"):
            return render_template("forgot_password.html", error="Invalid email")
        
        try:
            validate_email(request.form.get("email"))
        except EmailNotValidError:
            return render_template("forgot_password.html", error="Invalid email")
        
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email = %s",(request.form.get("email"),))
        rows = cur.fetchall()
        if not rows:
            cur.close()
            conn.close()
            return render_template("forgot_password.html", error="if email exists, we sent a reset link")
        token = secrets.token_urlsafe(32)
        token_hash = bcrypt.hashpw(token.encode('utf-8'),bcrypt.gensalt()).decode('utf-8')
        expires_at = datetime.utcnow() + timedelta(hours=1)
        cur.execute("DELETE FROM tokens WHERE user_id = %s",(rows[0][0],))
        cur.execute("INSERT INTO tokens(user_id, token_hash, expires_at) VALUES(%s, %s, %s)",(rows[0][0], token_hash, expires_at))
        conn.commit()
        cur.close()
        conn.close()
        
        msg = Message(
            subject='Reset password',
            sender=os.getenv('MAIL_USERNAME'),
            recipients=[rows[0][2]],
            body=f"Reset your password: http://localhost:5000/reset-password/{token}"
        )
        mail.send(msg)
        return redirect(f"/reset-password/{token}")
    return render_template("/forgot_password.html")

if __name__ == "__main__":
    app.run(debug=True)

