from configparser import ConfigParser

def config(filename='C:/Users/ayowale.olusanya_max/Documents/python_email_automate/flask__application/database.ini', section='local_postgresql'):
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
