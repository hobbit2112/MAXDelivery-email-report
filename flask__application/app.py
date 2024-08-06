from flask import Flask, request, render_template, redirect, url_for
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

        # Create queries table with createdAt column
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS queries (
            id SERIAL PRIMARY KEY,
            query TEXT NOT NULL,
            email VARCHAR(255) NOT NULL,
            createdAt TIMESTAMPTZ DEFAULT NOW()
        );
        ''')

        # Create reports table
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

        # Create recipients table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS recipients (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) NOT NULL,
            report_id INTEGER REFERENCES reports(id)
        );
        ''')

        # Create schedules table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS schedules (
            id SERIAL PRIMARY KEY,
            report_id INTEGER REFERENCES reports(id),
            schedule_time TIMESTAMPTZ NOT NULL,
            createdAt TIMESTAMPTZ DEFAULT NOW()
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
            # Handle user-created queries here
            pass
        
        elif action == 'schedule_report':
            # Handle report scheduling here
            pass

        # Existing code for processing user queries
        if query_text and email_receiver:
            params = config(section='remote_postgresql')
            remote_conn = psycopg2.connect(**params)
            remote_cursor = remote_conn.cursor()
            remote_cursor.execute(query_text)
            rows = remote_cursor.fetchall()
            colnames = [desc[0] for desc in remote_cursor.description]
            remote_cursor.close()
            remote_conn.close()

            # Convert the result into a DataFrame
            df = pd.DataFrame(rows, columns=colnames)

            # Store the report in the local database
            params = config(section='local_postgresql')
            local_conn = psycopg2.connect(**params)
            cursor = local_conn.cursor()

            # Insert report
            insert_report_query = '''
            INSERT INTO reports (query, email, csv_file_path)
            VALUES (%s, %s, %s) RETURNING id
            '''
            cursor.execute(insert_report_query, (query_text, email_receiver, ''))
            report_id = cursor.fetchone()[0]
            local_conn.commit()

            # Use a temporary file for the CSV
            with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as temp_file:
                csv_file_path = temp_file.name
                df.to_csv(csv_file_path, index=False)

            print(f"\nData saved to {csv_file_path}")

            # Update the report with the CSV file path
            update_report_query = '''
            UPDATE reports
            SET csv_file_path = %s
            WHERE id = %s
            '''
            cursor.execute(update_report_query, (csv_file_path, report_id))
            local_conn.commit()

            # Insert recipients
            insert_recipient_query = '''
            INSERT INTO recipients (email, report_id)
            VALUES (%s, %s)
            '''
            for email in emails:
                cursor.execute(insert_recipient_query, (email, report_id))
            local_conn.commit()

            print('Report, recipients, and CSV file path stored successfully.')

            # Store the query and emails in the local database with createdAt timestamp
            created_at = datetime.now()
            insert_query = '''
            INSERT INTO queries (query, email, createdAt)
            VALUES (%s, %s, %s)
            '''
            cursor.execute(insert_query, (query_text, email_receiver, created_at))
            local_conn.commit()

            # Asynchronously send emails
            executor.submit(send_emails, emails, csv_file_path)

            cursor.close()
            local_conn.close()

            return 'Emails are being sent.'

        return 'Invalid action selected.'

    except Exception as e:
        logging.error(f"Error processing query: {e}")
        return 'An error occurred while processing your request.'
    
    
@app.route('/view_reports')
def view_reports():
    try:
        params = config(section='local_postgresql')
        conn = psycopg2.connect(**params)
        cursor = conn.cursor()

        # Query to get all reports
        query = '''
        SELECT *
        FROM reports;
        '''
        cursor.execute(query)
        reports = cursor.fetchall()
        print(reports)

        # Close the connection
        cursor.close()
        conn.close()

        # Render the reports.html template with data
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
