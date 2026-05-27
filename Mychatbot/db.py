import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

conn = pymysql.connect(
    unix_socket=os.environ.get('DB_SOCKET'),
    user=os.environ.get('DB_USER'),
    password=os.environ.get('DB_PASSWORD'),
    database=os.environ.get('DB_NAME'),
    charset='utf8mb4',
    autocommit=True
)

def get_or_create_user(user_id):
    with conn.cursor() as cursor:
        sql = "SELECT * FROM user WHERE user_id=%s"
        cursor.execute(sql, (user_id,))
        result = cursor.fetchone()

        if not result:
            sql = "INSERT INTO user (user_id) VALUES (%s)"
            cursor.execute(sql, (user_id,))
            print("✅ user 생성됨")

    return user_id

def save_history(user_id, relation, situation):
    with conn.cursor() as cursor:
        sql = """
        INSERT INTO history (user_id, relation, situation)
        VALUES (%s, %s, %s)
        """
        cursor.execute(sql, (user_id, relation, situation))
        history_id = cursor.lastrowid

    print("✅ history 저장됨:", history_id)
    return history_id

def save_result(history_id, result_text):
    with conn.cursor() as cursor:
        sql = """
        INSERT INTO result (history_id, result)
        VALUES (%s, %s)
        """
        cursor.execute(sql, (history_id, result_text))

    print("✅ result 저장됨")

def get_user_history(user_id):

    with conn.cursor() as cursor:

        sql = """
        SELECT history.id, result.result, history.created_at
        FROM history
        JOIN result
        ON history.id = result.history_id
        WHERE history.user_id=%s
        ORDER BY history.created_at DESC
        LIMIT 5
        """

        cursor.execute(sql, (user_id,))

        results = cursor.fetchall()

    return results
