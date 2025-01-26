from flask import Flask, render_template, request, redirect, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
import os

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "your_secret_key")  # Use a secure key in production

# Database connection
def get_db_connection():
    return mysql.connector.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        user=os.environ.get('DB_USER', 'root'),       # Replace with your MySQL username
        password=os.environ.get('DB_PASSWORD', 'root69'), # Replace with your MySQL password
        database=os.environ.get('DB_NAME', 'blogging_platform')
    )

@app.route('/')
@app.route('/<int:blog_id>')
def index(blog_id=None):
    search_query = request.args.get('search')
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        if blog_id:  # If a blog_id is passed, we show the full blog
            cursor.execute("""
                SELECT blogs.id, blogs.title, blogs.content, blogs.category, bloggers.email AS author, blogs.image_url
                FROM blogs
                JOIN bloggers ON blogs.user_id = bloggers.id
                WHERE blogs.id = %s
            """, (blog_id,))
            blog = cursor.fetchone()
            conn.close()
            if blog:
                return render_template('index.html', blog=blog, search_query=search_query)
            else:
                flash("Blog not found.", "danger")
                return redirect('/')
        
        # If no blog_id is passed, we list the blogs
        if search_query:
            cursor.execute("""
                SELECT blogs.id, blogs.title, blogs.content, blogs.category, bloggers.email AS author, blogs.image_url
                FROM blogs
                JOIN bloggers ON blogs.user_id = bloggers.id
                WHERE blogs.title LIKE %s OR blogs.content LIKE %s
            """, (f'%{search_query}%', f'%{search_query}%'))
        else:
            cursor.execute("""
                SELECT blogs.id, blogs.title, blogs.content, blogs.category, bloggers.email AS author, blogs.image_url
                FROM blogs
                JOIN bloggers ON blogs.user_id = bloggers.id
            """)
        
        blogs = cursor.fetchall()
        conn.close()
        return render_template('index.html', blogs=blogs, search_query=search_query)
    
    except mysql.connector.Error as err:
        flash(f"Error: {err}", "danger")
        return render_template('index.html', blogs=[])

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        blogger_type = request.form['blogger_type']

        # Validate email and password
        if not email or not password or not blogger_type:
            flash("All fields are required!", "danger")
            return redirect('/register')
        
        if '@gmail.com' not in email:
            flash("Please enter a valid Gmail address.", "danger")
            return redirect('/register')

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "danger")
            return redirect('/register')

        # Hash password
        hashed_password = generate_password_hash(password)

        # Check if the email already exists
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM bloggers WHERE email = %s", (email,))
            existing_user = cursor.fetchone()

            if existing_user:
                flash("Email is already registered.", "danger")
                conn.close()
                return redirect('/register')

            cursor.execute(""" 
                INSERT INTO bloggers (email, password, blogger_type)
                VALUES (%s, %s, %s)
            """, (email, hashed_password, blogger_type))
            conn.commit()
            conn.close()
            flash("Registration successful! Please log in.", "success")
            return redirect('/login')
        except mysql.connector.Error as err:
            flash(f"Error: {err}", "danger")
            return redirect('/register')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # Check if email or password is blank
        if not email or not password:
            flash("Both email and password are required.", "danger")
            return redirect('/login')

        # Check credentials in database
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM bloggers WHERE email = %s", (email,))
            user = cursor.fetchone()
            conn.close()

            if user and check_password_hash(user['password'], password):
                # Store user information in session
                session['user_id'] = user['id']
                session['user_name'] = user['email']  # Store the user's email
                flash(f"Welcome, {user['email']}!", "success")
                return redirect('/blogger-dashboard')
            else:
                flash("Invalid email or password. Please try again.", "danger")
        except mysql.connector.Error as err:
            flash(f"Error: {err}", "danger")
    
    return render_template('login.html')

# Blogger dashboard route
@app.route('/blogger-dashboard')
def blogger_dashboard():
    if 'user_id' not in session:
        return redirect('/login')

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM blogs WHERE user_id = %s", (session['user_id'],))
        blogs = cursor.fetchall()
        conn.close()
        return render_template('blogger_dashboard.html', user_name=session['user_name'], blogs=blogs)
    except mysql.connector.Error as err:
        flash(f"Error: {err}", "danger")
        return redirect('/blogger-dashboard')

@app.route('/create-blog', methods=['GET', 'POST'])
def create_blog():
    if 'user_id' not in session:
        return redirect('/login')

    error_messages = {}

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        category = request.form.get('category', '').strip()
        image_url = request.form.get('image_url', '').strip() or '/static/images/placeholder.jpg'
        user_id = session['user_id']

        # Check for duplicate title (case insensitive)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM blogs WHERE LOWER(title) = LOWER(%s)", (title,))
        existing_blog = cursor.fetchone()
        if existing_blog:
            error_messages['title'] = "A blog with this title already exists."

        # Validate fields
        if not title:
            error_messages['title'] = "Title cannot be blank."
        elif len(title) > 100:  # Enforce title length limit on backend
            error_messages['title'] = "Title cannot exceed 100 characters."
        
        if not content:
            error_messages['content'] = "Content cannot be blank."
        elif len(content) > 5000:  # Enforce content length limit on backend
            error_messages['content'] = "Content cannot exceed 5000 characters."
        
        if not category:
            error_messages['category'] = "Please select a category."

        # Proceed with saving the blog if no errors
        if not error_messages:
            try:
                cursor.execute("""
                    INSERT INTO blogs (title, content, category, user_id, image_url)
                    VALUES (%s, %s, %s, %s, %s)
                """, (title, content, category, user_id, image_url))
                conn.commit()
                flash("Blog created successfully!", "success")
                return redirect('/create-blog')
            except Exception as err:
                flash(f"Error: {err}", "danger")
                return redirect('/create-blog')
            finally:
                conn.close()  # Ensure the connection is closed after use

    return render_template('create_blog.html', error_messages=error_messages)

@app.route('/edit-blog/<int:blog_id>', methods=['GET', 'POST'])
def edit_blog(blog_id):
    if 'user_id' not in session:
        flash("Please log in to access this page.", "danger")
        return redirect('/login')

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM blogs WHERE id = %s AND user_id = %s", (blog_id, session['user_id']))
        blog = cursor.fetchone()

        if not blog:
            flash("Blog not found or unauthorized access.", "danger")
            return redirect('/blogger-dashboard')

        if request.method == 'POST':
            title = request.form['title']
            content = request.form['content']
            category = request.form['category']
            image_url = request.form.get('image_url', blog['image_url'])

            # Validate content length
            if len(content) > 5000:
                flash("Content cannot exceed 5000 characters.", "danger")
                return render_template('edit_blog.html', blog=blog)

            # Validate unique title
            cursor.execute("SELECT id FROM blogs WHERE title = %s AND id != %s", (title, blog_id))
            existing_blog = cursor.fetchone()
            if existing_blog:
                flash("Title must be unique. Please choose a different title.", "danger")
                return render_template('edit_blog.html', blog=blog)

            # Update the blog entry
            cursor.execute("""
                UPDATE blogs
                SET title = %s, content = %s, category = %s, image_url = %s
                WHERE id = %s
            """, (title, content, category, image_url, blog_id))
            conn.commit()

            flash("Blog updated successfully!", "success")
            return redirect(f'/edit-blog/{blog_id}')

    except mysql.connector.Error as err:
        flash(f"Database Error: {err}", "danger")
    finally:
        conn.close()

    return render_template('edit_blog.html', blog=blog)

@app.route('/delete-blog/<int:blog_id>', methods=['POST'])
def delete_blog(blog_id):
    if 'user_id' not in session:
        flash("You must be logged in to perform this action.", "danger")
        return redirect('/login')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Ensure the blog belongs to the logged-in user
        cursor.execute("DELETE FROM blogs WHERE id = %s AND user_id = %s", (blog_id, session['user_id']))
        if cursor.rowcount == 0:  # Check if any row was deleted
            flash("Blog not found or you are not authorized to delete it.", "danger")
        else:
            conn.commit()
            flash("Blog deleted successfully!", "success")
        
    except mysql.connector.Error as err:
        flash(f"Error while deleting the blog: {err}", "danger")
    finally:
        conn.close()

    return redirect('/blogger-dashboard')

# Route for logout
@app.route('/logout')
def logout():
    session.clear()  # Clear session data
    flash("You have been logged out.", "info")
    return redirect('/login')

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
