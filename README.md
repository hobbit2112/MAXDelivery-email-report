# **Flask Report Automation**

This Flask application allows users to submit SQL queries, schedule reports, and manage email notifications. The application connects to a PostgreSQL database, processes queries, and sends email reports with CSV attachments. It also provides functionalities to view and manage reports and schedules.

# **Features**

Submit Queries: Execute SQL queries and store results in the database.
Schedule Reports: Schedule reports to be generated and sent via email.
View Reports: View a list of generated reports.
Email Notifications: Send email notifications with attached CSV files.

# **Installation**

1.  ## **Clone the Repository**:

```bash
git clone https://github.com/username/repository.git
cd repository
```

2.  ## **Install Dependencies**:
Ensure you have Python and pip installed. Install the required packages using:

```bash
pip install -r requirements.txt
```

3.  ## **Configuration**:

### **database.ini**:  
Store your database credentials in a file named   `database.ini`   with the following format:

``` ini
  [local_postgresql]
  host = localhost
  port = 5432
  database = postgres
  user = postgres
  password = password`

  [remote_postgresql]
  host = 34.90.95.17
  port = 5432
  database = v2production
  user = datateam
  password = *************
```
### **config.py**: 
This file is used to read database credentials from database.ini. Ensure `config.py` is configured correctly:
```python
from configparser import ConfigParser

def config(filename='C:/Users/ayowale.olusanya_max/Documents/python_email_automate/database.ini', section='local_postgresql'):
    parser = ConfigParser()
    parser.read(filename)

    db = {}
    if parser.has_section(section):
        params = parser.items(section)
        for param in params:
            db[param[0]] = param[1]
    else:
        raise Exception(f'Section {section} not found in the {filename} file')

    return db
```  
4. ## **Run the Application**:

```
python app.py
```
The Flask app will start and be accessible at   `http://127.0.0.1:5000`.

# **Usage**
Home Page (/): Display a form for submitting queries or scheduling reports.
Submit Query (`/submit_query`): Handle form submissions for queries, scheduling, and email notifications.
View Reports (`/view_reports`): Display a list of all generated reports.

# **Form Fields**
### Action: Specify the action to perform (`retrieve_report`, `user_query`, `schedule_report`).
### Query: SQL query to execute.
### Email: Email addresses to receive the report, separated by commas.

# **Development**
1. ## **Create Tables**:
The application automatically creates necessary tables in the local PostgreSQL database on startup.

2.  ## **Logging**:
Logs are captured for debugging and error tracking.

3.  ## **Asynchronous Email Sending**:
Emails are sent asynchronously using `ThreadPoolExecutor` to avoid blocking the main thread.

# **Dependencies**
-Flask
-pandas
-psycopg2
-yagmail
-Logging
-Other standard Python libraries
# **Contributing**
1.  Fork the repository.
2.  Create a new branch (`git checkout -b feature-branch`).
3.  Commit your changes (`git commit -am 'Add new feature'`).
4.  Push to the branch (`git push origin feature-branch`).
5.  Create a new Pull Request.
# License
This project is licensed under the MIT License. See the LICENSE file for details.

# Contact
For questions or issues, please contact ayowale.olusanya@maxdrive.ai.

