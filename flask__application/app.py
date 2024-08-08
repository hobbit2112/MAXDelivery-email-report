from flask import Flask, request, render_template, redirect, url_for, jsonify
import yagmail
import pandas as pd
import psycopg2
import re
import logging
from concurrent.futures import ThreadPoolExecutor
import os
import tempfile
from datetime import datetime
from config import config

# Initialize the Flask app
app = Flask(__name__)

# ThreadPoolExecutor for asynchronous tasks
executor = ThreadPoolExecutor(max_workers=4)

# Function to create tables if they don't exist
def create_tables():
    try:
        params = config(section='local_postgresql')
        conn = psycopg2.connect(**params)
        cursor = conn.cursor()

        # Create tables
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS queries (
            id SERIAL PRIMARY KEY,
            query TEXT NOT NULL,
            email VARCHAR(255) NOT NULL,
            createdAt TIMESTAMPTZ DEFAULT NOW()
        );
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id SERIAL PRIMARY KEY,
            query TEXT NOT NULL,
            email VARCHAR(255) NOT NULL,
            schedule_time TIMESTAMPTZ,
            csv_file_path TEXT,
            createdAt TIMESTAMPTZ DEFAULT NOW()
        );
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS recipients (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) NOT NULL,
            report_id INTEGER REFERENCES reports(id)
        );
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS scheduled_reports (
            id SERIAL PRIMARY KEY,
            query TEXT NOT NULL,
            email TEXT NOT NULL,
            day_of_week VARCHAR(20) NOT NULL,
            hour_of_day INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        ''')

        conn.commit()
    except Exception as e:
        logging.error(f"Error creating tables: {e}")
    finally:
        cursor.close()
        conn.close()

# Call the function to create the tables
create_tables()

@app.route('/')
def index():
    return render_template('form.html')

@app.route('/submit_query', methods=['POST'])
def submit_query():
    try:
        action = request.form.get('action')
        query_text = request.form.get('query')
        email_receiver = request.form.get('email')
        emails = [email.strip() for email in re.split('[, ]+', email_receiver) if email.strip()]

        if action == 'retrieve_report':
            return redirect(url_for('view_reports'))

        elif action == 'user_query':
            return redirect(url_for('query'))

        elif action == 'schedule_report':
            day = request.form.get('day')
            hour = request.form.get('hour')
            schedule_time = f'{day} at {hour}:00'

            save_scheduled_report(query_text, email_receiver, day, hour)
            return f'Report scheduled for {schedule_time}.'

        if query_text and emails:
            df = execute_remote_query(query_text)
            csv_file_path = save_report_locally(df, query_text, email_receiver)
            save_query_and_recipients(query_text, emails, csv_file_path)

            executor.submit(send_emails, emails, csv_file_path)
            return 'Emails are being sent.'

        return 'Invalid action selected.'

    except Exception as e:
        logging.error(f"Error processing query: {e}")
        return 'An error occurred while processing your request.'

def save_scheduled_report(query_text, email_receiver, day, hour):
    """ Save the scheduled report to the local database """
    params = config(section='local_postgresql')
    with psycopg2.connect(**params) as local_conn:
        with local_conn.cursor() as cursor:
            insert_schedule_query = '''
            INSERT INTO scheduled_reports (query, email, day_of_week, hour_of_day)
            VALUES (%s, %s, %s, %s)
            '''
            cursor.execute(insert_schedule_query, (query_text, email_receiver, day, hour))
        local_conn.commit()

def execute_remote_query(query_text):
    """ Execute the query on the remote database and return the results as a DataFrame """
    params = config(section='remote_postgresql')
    with psycopg2.connect(**params) as remote_conn:
        with remote_conn.cursor() as remote_cursor:
            remote_cursor.execute(query_text)
            rows = remote_cursor.fetchall()
            colnames = [desc[0] for desc in remote_cursor.description]
    return pd.DataFrame(rows, columns=colnames)

def save_report_locally(df, query_text, email_receiver):
    """ Save the report and query in the local database and return the CSV file path """
    params = config(section='local_postgresql')
    with psycopg2.connect(**params) as local_conn:
        with local_conn.cursor() as cursor:
            insert_report_query = '''
            INSERT INTO reports (query, email, csv_file_path)
            VALUES (%s, %s, %s) RETURNING id
            '''
            cursor.execute(insert_report_query, (query_text, email_receiver, ''))
            report_id = cursor.fetchone()[0]
            local_conn.commit()

            with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as temp_file:
                csv_file_path = temp_file.name
                df.to_csv(csv_file_path, index=False)

            update_report_query = '''
            UPDATE reports
            SET csv_file_path = %s
            WHERE id = %s
            '''
            cursor.execute(update_report_query, (csv_file_path, report_id))
            local_conn.commit()
    return csv_file_path

def save_query_and_recipients(query_text, emails, csv_file_path):
    """ Save the query and associated recipients to the local database """
    params = config(section='local_postgresql')
    with psycopg2.connect(**params) as local_conn:
        with local_conn.cursor() as cursor:
            created_at = datetime.now()
            insert_query = '''
            INSERT INTO queries (query, email, createdAt)
            VALUES (%s, %s, %s)
            '''
            cursor.execute(insert_query, (query_text, ', '.join(emails), created_at))
            local_conn.commit()

            insert_recipient_query = '''
            INSERT INTO recipients (email, report_id)
            VALUES (%s, %s)
            '''
            for email in emails:
                cursor.execute(insert_recipient_query, (email, cursor.lastrowid))
            local_conn.commit()

def send_emails(emails, file_path):
    """ Send emails with the generated report as an attachment """
    from_address = "ayowale.olusanya@maxdrive.ai"
    subject = "Savings Email"
    body = "Dear Ayowole, Attached is the savings data for the month."
    app_password = "hamz mxlf hycm vphx"

    yag = yagmail.SMTP(from_address, app_password)
    for email in emails:
        yag.send(to=email, subject=subject, contents=body, attachments=file_path)
        print(f"Email sent successfully to {email}")

    os.remove(file_path)

@app.route('/query')
def query():
    try:
        data = get_queries_and_emails()
        return render_template('query.html', queries=data['queries'], emails=data['emails'])
    except Exception as e:
        logging.error(f"Error rendering query page: {e}")
        return 'An error occurred while rendering the page.'

@app.route('/get_queries_and_emails', methods=['GET'])
def get_queries_and_emails():
    try:
        params = config(section='local_postgresql')
        with psycopg2.connect(**params) as conn:
            with conn.cursor() as cursor:
                cursor.execute('SELECT id, query FROM queries')
                queries = cursor.fetchall()

                cursor.execute('SELECT DISTINCT email FROM queries')
                emails = [email[0] for email in cursor.fetchall()]

        return {'queries': [{'id': q[0], 'text': q[1]} for q in queries], 'emails': emails}

    except Exception as e:
        logging.error(f"Error fetching queries and emails: {e}")
        return {'queries': [], 'emails': []}

@app.route('/update_run_query', methods=['POST'])
def update_run_query():
    try:
        data = request.get_json()
        query_text = data.get('query_text')
        email_receiver = data.get('email_receiver')

        if query_text and email_receiver:
            df = execute_remote_query(query_text)
            csv_file_path = save_report_locally(df, query_text, email_receiver)
            save_query_and_recipients(query_text, email_receiver.split(','), csv_file_path)

            params = config(section='local_postgresql')
            with psycopg2.connect(**params) as local_conn:
                with local_conn.cursor() as cursor:
                    cursor.execute('SELECT id, query, email, createdAt FROM queries')
                    all_queries = cursor.fetchall()

            response_data = [{'id': q[0], 'query': q[1], 'email': q[2], 'created_at': q[3].strftime('%Y-%m-%d %H:%M:%S')}
                             for q in all_queries]

            return jsonify(data=response_data)

        return jsonify(error='Invalid input'), 400

    except Exception as e:
        logging.error(f"Error processing query: {e}")
        return jsonify(error='An error occurred while processing your request.'), 500

@app.route('/view_reports')
def view_reports():
    try:
        params = config(section='local_postgresql')
        with psycopg2.connect(**params) as conn:
            with conn.cursor() as cursor:
                cursor.execute('SELECT * FROM reports')
                reports = cursor.fetchall()

        return render_template('reports.html', tables=[reports])
    except Exception as e:
        logging.error(f"Error fetching reports: {e}")
        return 'An error occurred while fetching the reports.'


def send_emails(emails, file_path):
    from_address = "ayowale.olusanya@maxdrive.ai"
    subject = "Savings Email"
    body = "Dear Ayowole, Attached is the savings data for the month."

    # Use the generated App Password here
    app_password = "hamz mxlf hycm vphx"

    yag = yagmail.SMTP(from_address, app_password)

    for email in emails:
        yag.send(
            to=email,
            subject=subject,
            contents=body,
            attachments=file_path,
        )
        print(f"\nEmail sent successfully to {email}")

    # Remove the temporary file after sending the emails
    os.remove(file_path)

if __name__ == '__main__':
    app.run(debug=True)
