from flask import Flask, render_template, request
import mysql.connector

app = Flask(__name__)

def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",          
        password="ghunwmkk2",
        database="fake_users_data"
    )

@app.route("/", methods=["GET"])
def index():
    locale_id = int(request.args.get("locale_id", 1))
    seed = int(request.args.get("seed", 12345))
    batch = int(request.args.get("batch", 0))
    batch_size = 10

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT id, code FROM locales")
    locales = cursor.fetchall()

    cursor.callproc(
        "generate_fake_user_batch",
        [locale_id, seed, batch, batch_size]
    )

    users = []
    for result in cursor.stored_results():
        users = result.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "index.html",
        users=users,
        locales=locales,
        locale_id=locale_id,
        seed=seed,
        batch=batch
    )

if __name__ == "__main__":
    app.run(debug=True)
