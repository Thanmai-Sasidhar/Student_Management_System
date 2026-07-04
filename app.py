from flask import Flask, request, redirect, url_for, render_template, flash, session,jsonify
from flask import send_file
from io import BytesIO
from flask_session import Session
from otp import getotp
from cmail import send_mail
from stoken import endata, dndata
from mysql.connector import connection
import flask_excel as excel
import re

mydb = connection.MySQLConnection(
    user='flaskuser',
    password='password',
    host='localhost',
    database='snm'
)
app = Flask(__name__)
app.secret_key = 'Code000'

app.config['SESSION_TYPE'] = 'filesystem'
Session(app)
excel.init_excel(app)


# ---------------- HOME ---------------- #

@app.route('/')
def home():
    return render_template('welcome.html')


# ---------------- REGISTER ---------------- #

@app.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'GET':
        return render_template('register.html')

    username = request.form['username']
    useremail = request.form['useremail']
    userpassword = request.form['userpassword']
    userphone = request.form['userphone']

    try:
        cursor = mydb.cursor(buffered=True)

        cursor.execute(
            'select count(*) from userdata where useremail=%s',
            [useremail]
        )

        email_count = cursor.fetchone()[0]
        cursor.close()

    except Exception as e:
        print(e)
        flash("Could not verify email")
        return redirect(url_for('home'))

    if email_count == 0:

        gotp = getotp()

        userdata = {
            "username": username,
            "useremail": useremail,
            "userpassword": userpassword,
            "userphone": userphone,
            "serverotp": gotp
        }

        subject = "OTP Verification"
        body = f"Your OTP is {gotp}"

        send_mail(
            to=useremail,
            subject=subject,
            body=body
        )

        flash("OTP sent successfully")

        return redirect(
            url_for(
                'otpverify',
                serverdata=endata(userdata)
            )
        )

    else:
        flash("Email already exists")
        return redirect(url_for('home'))


# ---------------- OTP VERIFY ---------------- #

@app.route('/otpverify/<serverdata>', methods=['GET', 'POST'])
def otpverify(serverdata):

    if request.method == 'POST':

        userotp = request.form['otp']

        try:
            d_data = dndata(serverdata)

        except Exception as e:
            print(e)
            flash("Invalid Data")
            return redirect(
                url_for(
                    'otpverify',
                    serverdata=serverdata
                )
            )

        if userotp == d_data['serverotp']:

            try:

                cursor = mydb.cursor(buffered=True)

                cursor.execute(
                    '''
                    insert into userdata
                    (username,useremail,password,phone_num)
                    values(%s,%s,%s,%s)
                    ''',
                    [
                        d_data['username'],
                        d_data['useremail'],
                        d_data['userpassword'],
                        d_data['userphone']
                    ]
                )

                mydb.commit()
                cursor.close()

            except Exception as e:
                print(e)
                flash("Registration Failed")

            else:
                flash("Registration Successful")
                return redirect(url_for('home'))

        else:
            flash("Invalid OTP")

    return render_template("otpverify.html")





# ---------------- LOGIN ---------------- #

@app.route('/login', methods=['POST'])
def login():

    useremail = request.form['useremail']
    password = request.form['password']

    try:

        cursor = mydb.cursor(buffered=True)

        cursor.execute(
            "select password from userdata where useremail=%s",
            [useremail]
        )

        data = cursor.fetchone()

        cursor.close()

    except Exception as e:
        print(e)
        flash("Database Error")
        return redirect(url_for('home'))

    if data is None:
        flash("Email not registered")
        return redirect(url_for('home'))

    if data[0] == password:

        session['useremail'] = useremail

        flash("Login Successful")

        return redirect(url_for('dashboard'))

    else:
        flash("Wrong Password")
        return redirect(url_for('home'))


# ---------------- DASHBOARD ---------------- #
@app.route('/deletenote/<int:note_id>')
def deletenote(note_id):

    cursor = mydb.cursor(buffered=True)

    cursor.execute(
        "DELETE FROM notes WHERE note_id=%s AND useremail=%s",
        (note_id, session['useremail'])
    )

    mydb.commit()
    cursor.close()

    flash("Note deleted successfully")

    return redirect(url_for('viewallnotes'))


@app.route('/updatenote/<int:note_id>', methods=['GET', 'POST'])
def updatenote(note_id):

    cursor = mydb.cursor(dictionary=True)

    if request.method == 'POST':

        title = request.form['title']
        description = request.form['description']

        cursor.execute(
            """
            UPDATE notes
            SET title=%s, description=%s
            WHERE note_id=%s AND useremail=%s
            """,
            (title, description, note_id, session['useremail'])
        )

        mydb.commit()
        cursor.close()

        flash("Note updated successfully")

        return redirect(url_for('viewallnotes'))

    cursor.execute(
        "SELECT * FROM notes WHERE note_id=%s AND useremail=%s",
        (note_id, session['useremail'])
    )

    note = cursor.fetchone()
    cursor.close()

    return render_template('updatenote.html', note=note)


@app.route('/dashboard')
def dashboard():

    if 'useremail' not in session:
        flash("Please login first")
        return redirect(url_for('home'))

    return render_template('dashboard.html')


# ---------------- ADD NOTES ---------------- #

@app.route('/viewnote/<int:note_id>')
def viewnote(note_id):

    if 'useremail' not in session:
        return redirect(url_for('home'))

    cursor = mydb.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM notes WHERE note_id=%s AND useremail=%s",
        (note_id, session['useremail'])
    )

    note = cursor.fetchone()
    cursor.close()

    return render_template('viewnote.html', note=note)

@app.route('/addnotes', methods=['GET', 'POST'])
def addnotes():

    if 'useremail' not in session:
        flash("Please login first")
        return redirect(url_for('home'))

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']

        try:
            cursor = mydb.cursor(buffered=True)

            cursor.execute(
                "INSERT INTO notes(title, description, useremail) VALUES(%s,%s,%s)",
                (title, description, session['useremail'])
            )

            mydb.commit()
            cursor.close()

            flash("Note added successfully")
            return redirect(url_for('viewallnotes'))

        except Exception as e:
            print(e)
            flash("Unable to save note")

    return render_template('addnotes.html')

# ---------------- VIEW NOTES ---------------- #

@app.route('/viewallnotes')
def viewallnotes():

    if 'useremail' not in session:
        flash("Please login first")
        return redirect(url_for('home'))

    try:
        cursor = mydb.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM notes WHERE useremail=%s",
            (session['useremail'],)
        )

        notes = cursor.fetchall()
        cursor.close()

        return render_template("viewallnotes.html", notes=notes)

    except Exception as e:
        print(e)
        flash("Unable to fetch notes")
        return redirect(url_for('dashboard'))
@app.route('/get_excel_data')
def get_excel_data():
    cursor = mydb.cursor(dictionary=True)
    cursor.execute("SELECT * FROM notes WHERE useremail=%s", (session['useremail'],))
    notes = cursor.fetchall()
    cursor.close()
    if notes:
        headings = list(notes[0].keys())
        data = [list(note.values()) for note in notes]
        excel_data = [headings] + data
    else:
        excel_data = [["id", "title", "description", "created_at", "useremail"]]
    return excel.make_response_from_array(excel_data, "xlsx")
# ---------------- LOGOUT ---------------- #

@app.route('/logout')
def logout():

    session.pop('useremail', None)

    flash("Logged Out Successfully")

    return redirect(url_for('home'))


@app.route('/uploadfile', methods=['GET', 'POST'])
def uploadfile():

    if 'useremail' not in session:
        flash("Please login first")
        return redirect(url_for('home'))

    if request.method == 'POST':

        file_info = request.files['file']

        if file_info.filename == '':
            flash("Please choose a file")
            return redirect(url_for('uploadfile'))

        fname = file_info.filename
        fdata = file_info.read()

        try:
            cursor = mydb.cursor(buffered=True)

            cursor.execute(
                """
                INSERT INTO files(filename, filedata, useremail)
                VALUES(%s, %s, %s)
                """,
                (fname, fdata, session['useremail'])
            )

            # Get inserted file ID
            fileid = cursor.lastrowid

            cursor.execute(
                """
                INSERT INTO notes(title, description, useremail)
                VALUES(%s, %s, %s)
                """,
                (fname, f"File uploaded with ID: {fileid}", session['useremail'])
            )

            mydb.commit()
            cursor.close()

            flash("File uploaded successfully!")

        except Exception as e:
            print(e)
            mydb.rollback()
            flash("File upload failed!")

        return redirect(url_for('uploadfile'))

    # GET Request
    return render_template("uploadfile.html")

@app.route('/viewallfiles')
def viewallfiles():

    if 'useremail' not in session:
        flash("Please login first")
        return redirect(url_for('home'))

    try:
        cursor = mydb.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM files WHERE useremail=%s",
            (session['useremail'],)
        )

        files = cursor.fetchall()

        print(files)   # Debug

        cursor.close()

        return render_template("viewallfiles.html", files=files)

    except Exception as e:
        print(e)
        flash("Unable to fetch files")
        return redirect(url_for('dashboard'))
    
@app.route('/viewfile/<int:fileid>')
def viewfile(fileid):

    print("File ID:", fileid)

    if 'useremail' not in session:
        flash("Please login first")
        return redirect(url_for('home'))

    try:
        cursor = mydb.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM files WHERE fileid=%s AND useremail=%s",
            (fileid, session['useremail'])
        )

        file = cursor.fetchone()
        print(file)

        cursor.close()

        if file is None:
            flash("File not found")
            return redirect(url_for('viewallfiles'))

        return render_template("viewfile.html", file=file)

    except Exception as e:
        print("ERROR:", e)
        flash("Unable to fetch file")
        return redirect(url_for('dashboard'))
    
@app.route('/updatefile/<int:fileid>', methods=['GET', 'POST'])
def updatefile(fileid):

    if 'useremail' not in session:
        flash("Please login first")
        return redirect(url_for('home'))

    cursor = mydb.cursor(dictionary=True)

    if request.method == 'POST':

        file_info = request.files['file']

        if file_info.filename == "":
            flash("Please choose a file")
            return redirect(url_for('updatefile', fileid=fileid))

        fname = file_info.filename
        fdata = file_info.read()

        cursor.execute(
            """
            UPDATE files
            SET filename=%s,
                filedata=%s
            WHERE fileid=%s
            AND useremail=%s
            """,
            (fname, fdata, fileid, session['useremail'])
        )

        mydb.commit()
        cursor.close()

        flash("File updated successfully")
        return redirect(url_for('viewallfiles'))

    cursor.execute(
        """
        SELECT *
        FROM files
        WHERE fileid=%s
        AND useremail=%s
        """,
        (fileid, session['useremail'])
    )

    file = cursor.fetchone()
    cursor.close()

    return render_template("updatefile.html", file=file)


@app.route('/deletefile/<int:fileid>')
def deletefile(fileid):

    if 'useremail' not in session:
        flash("Please login first")
        return redirect(url_for('home'))

    cursor = mydb.cursor(buffered=True)

    cursor.execute(
        """
        DELETE FROM files
        WHERE fileid=%s
        AND useremail=%s
        """,
        (fileid, session['useremail'])
    )

    mydb.commit()
    cursor.close()

    flash("File deleted successfully")

    return redirect(url_for('viewallfiles'))

@app.route('/downloadfile/<int:fileid>')
def downloadfile(fileid):
    if 'useremail' not in session:
        flash("Please login first")
        return redirect(url_for('home'))

    cursor = mydb.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM files WHERE fileid=%s AND useremail=%s",
        (fileid, session['useremail'])
    )

    file = cursor.fetchone()
    cursor.close()

    if file is None:
        flash("File not found")
        return redirect(url_for('viewallfiles'))

    return send_file(
        BytesIO(file['filedata']),
        download_name=file['filename'],
        as_attachment=True
    )
@app.route('/search', methods=['POST'])
def search():

    if 'useremail' not in session:
        flash("Please login first")
        return redirect(url_for('home'))

    try:
        user_search = request.form['query'].strip()

        cursor = mydb.cursor(dictionary=True)

        cursor.execute("""
            SELECT *
            FROM notes
            WHERE useremail=%s
            AND (
                title LIKE %s
                OR description LIKE %s
            )
        """,
        (
            session['useremail'],
            f"%{user_search}%",
            f"%{user_search}%"
        ))

        notes = cursor.fetchall()
        cursor.close()

        return render_template("viewallnotes.html", notes=notes)

    except Exception as e:
        print(e)
        flash("Database Error")
        return redirect(url_for('dashboard'))
    
@app.route('/forgotpassword', methods=['GET', 'POST'])
def forgotpassword():
    if request.method == 'POST':
        forgot_email = request.form['useremail']
        try:
            cursor = mydb.cursor(buffered=True)
            cursor.execute(
                "SELECT * FROM userdata WHERE useremail=%s",
                [forgot_email]
            )
            email_data = cursor.fetchone()
            cursor.close()

            if email_data:  # ✅ correct check
                subject = 'Password Reset Request'
                body = f'Click the link below to reset your password: {url_for("newpassword", data=endata(forgot_email), _external=True)}'

                send_mail(to=forgot_email, subject=subject, body=body)

                flash("Password reset link sent to your email.")
                return redirect(url_for('forgotpassword'))  # ✅ correct route name

            else:
                flash("Email not registered.")
                return redirect(url_for('forgotpassword'))

        except Exception as e:
            print(e)
            flash("Database Error")
            return redirect(url_for('forgotpassword'))

    return render_template('forgot.html')
from flask import jsonify

@app.route("/newpassword/<data>", methods=["GET", "PUT"])
def newpassword(data):

    print("Method:", request.method)

    try:
        forgot_email = dndata(data)
        print("Email:", forgot_email)
    except Exception as e:
        print(e)
        flash("Invalid reset link")
        return redirect(url_for("forgotpassword"))

    if request.method == "GET":
        return render_template("newpassword.html")

    if request.method == "PUT":
        try:
            newdata = request.get_json()
            print(newdata)

            npassword = newdata.get("newpassword")
            cpassword = newdata.get("confirmpassword")

            if npassword != cpassword:
                return jsonify({
                    "message": "Passwords do not match"
                }), 400

            cursor = mydb.cursor(buffered=True)

            cursor.execute(
                "UPDATE userdata SET password=%s WHERE useremail=%s",
                (npassword, forgot_email)
            )

            mydb.commit()
            cursor.close()

            return jsonify({
                "message": "Password updated successfully"
            }), 200

        except Exception as e:
            print(e)
            return jsonify({
                "message": "Database Error"
            }), 500
if __name__ == "__main__":
    app.run(debug=True)
