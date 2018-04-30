from __future__ import print_function

import decimal
import json
import os
import boto3
from botocore.exceptions import ClientError
from flask import Flask, render_template, request, flash, session, redirect, url_for
from datetime import datetime
from uuid import uuid4

app = Flask(__name__)
app.config.from_object(__name__)

app.config.update(dict(
    DATABASE=os.path.join(app.root_path, 'tasks.db'),
    SECRET_KEY='task_development_key',
    USERNAME='admin',
    PASSWORD='default',
    SQLALCHEMY_DATABASE_URI='sqlite:////' + os.path.join(app.root_path, 'tasks.db')
))

region = os.getenv("AWS_REGION", "us-west-1")
dynamodb_endpoint = os.getenv("DYNAMO_DB_URL", "http://localhost:8000")

dynamodb = boto3.resource('dynamodb', region_name=region, endpoint_url=dynamodb_endpoint)


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            if o % 1 > 0:
                return float(o)
            else:
                return int(o)
        return super(DecimalEncoder, self).default(o)


class TaskRepository:

    def __init__(self, username):
        self.username = username

    def tasks(self):
        u = UserRepository(username=self.username)
        item = u.find_one()
        if "tasks" in item:
            return item["tasks"]
        else:
            return []

    def find_by_id(self, id):
        u = UserRepository(username=self.username)
        item = u.find_one()
        if "tasks" in item:
            tasks = item["tasks"]
            task_id = -1;
            for idx in range(len(item["tasks"])):
                if tasks[idx]["id"] == id:
                    task_id = idx
                    break
            if task_id < len(tasks):
                return tasks[task_id]
            else:
                raise Exception("Invalid task id")

    def add_task(self, title, description):
        table = dynamodb.Table('Users')
        u = UserRepository(username=self.username)
        item = u.find_one()
        tasks = []
        task = {
            'id' : str(uuid4()),
            'title': title,
            'description': description,
            'created_date': datetime.utcnow().isoformat()
        }
        if "tasks" in item:
            tasks = item["tasks"]
            tasks.append(task)
        else:
            tasks.append(task)
        response = table.update_item(
            Key={
                'username': self.username
            },
            UpdateExpression="set tasks= :a",
            ExpressionAttributeValues={
                ':a': tasks
            },
            ReturnValues="UPDATED_NEW"
        )
        print("UpdateItem succeeded:")
        print(json.dumps(response, indent=4, cls=DecimalEncoder))

    def edit_task(self, id, title, description, done):
        table = dynamodb.Table('Users')
        ur = UserRepository(username= self.username)
        u = ur.find_one()
        if "tasks" in u:
            for task in u["tasks"]:
                if task["id"] == id:
                    task["title"] = title
                    task["description"] = description
                    task["done"] = done
                    task["modified_date"] = datetime.utcnow().isoformat()
                    response = table.put_item(Item=u)
                    print(json.dumps(response, indent=4, cls=DecimalEncoder))
                    break
        print("Task updated successfully")

    def delete_task(self, id):
        table = dynamodb.Table('Users')
        ur = UserRepository(username=self.username)
        u = ur.find_one()
        tasks = u["tasks"]
        task_id = -1;
        for idx in range(len(tasks)):
            if tasks[idx]["id"] == id:
                task_id = idx
                break
        if task_id < len(tasks):
            u["tasks"].pop(task_id)
            response = table.put_item(Item=u)
            print(json.dumps(response, indent=4, cls=DecimalEncoder))
        else:
            raise Exception("Invalid task id")

class UserRepository:

    def __init__(self, username):
        self.username = username

    def find_one(self):
        table = dynamodb.Table('Users')
        try:
            response = table.get_item(
                Key={
                    'username': self.username
                }
            )
        except ClientError as e:
            print(e.response['Error']['Message'])
        else:
            return response['Item']

    def register(self, password, email_addr):
        table = dynamodb.Table('Users')
        response = table.put_item(
            Item={
                'username': self.username,
                'password': password,
                'email_addr': email_addr
            }
        )
        print('Registration successful')
        print(json.dumps(response, indent=4, cls=DecimalEncoder))


# db_connection = DatabaseConnection(app.config['DATABASE'])

# @app.cli.command('initdb')
# def initdb_command():
#     with app.open_resource('schema.sql', mode='r') as f:
#         db_connection.init_db(f.read())

@app.cli.command('init_users')
def init_users_cmd():
    users_table = dynamodb.create_table(TableName='Users',
                                        KeySchema=[
                                            {
                                                'AttributeName': 'username',
                                                'KeyType': 'HASH'
                                            }
                                        ],
                                        AttributeDefinitions=[
                                            {
                                                'AttributeName': 'username',
                                                'AttributeType': 'S'
                                            }
                                        ],
                                        ProvisionedThroughput={
                                            'ReadCapacityUnits': 5,
                                            'WriteCapacityUnits': 5
                                        })

    print('User Table Status', users_table.table_status)


@app.cli.command('init_tasks')
def init_tasks_cmd():
    tasks_table = dynamodb.create_table(TableName='Tasks',
                                        KeySchema=[
                                            {
                                                'AttributeName': 'username',
                                                'KeyType': 'HASH'
                                            },
                                            {
                                                'AttributeName': 'title',
                                                'KeyType': 'RANGE'
                                            }
                                        ],
                                        AttributeDefinitions=[
                                            {
                                                'AttributeName': 'username',
                                                'AttributeType': 'S'
                                            },
                                            {
                                                'AttributeName': 'title',
                                                'AttributeType': 'S'
                                            }
                                        ],
                                        ProvisionedThroughput={
                                            'ReadCapacityUnits': 5,
                                            'WriteCapacityUnits': 5
                                        })

    print('Tasks Table Status', tasks_table.table_status)


@app.route("/")
def index():
    return render_template("login.html")


@app.route("/register", methods=["POST", "GET"])
def register():
    if request.method == 'GET':
        return render_template("register.html")
    else:
        username = request.form["username"]
        password = request.form["password"]
        email_addr = request.form["email_addr"]
        ur = UserRepository(username=username)
        try:
            ur.register(password=password, email_addr=email_addr)
        except Exception as e:
            flash(e.message)
        return redirect(url_for("login"))


@app.route("/login", methods=["POST", "GET"])
def login():
    error = None
    if request.method == 'GET':
        return render_template("login.html")
    else:
        username = request.form["username"]
        password = request.form["password"]
        ur = UserRepository(username=username)
        tr = TaskRepository(username=username)
        u = ur.find_one()
        if u and u["password"] == password:
            session['username'] = username
            tasks = []
            if "tasks" in u:
                tasks = u["tasks"]
            return render_template("tasks.html", tasks=tasks)
        else:
            flash("Invalid credentials")
            return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.pop('username', None)
    return redirect(url_for("login"))


@app.route("/tasks")
def tasks():
    ur = UserRepository(username=session['username'])
    tr = TaskRepository(username=session['username'])
    u = ur.find_one()
    tsks = tr.tasks()
    return render_template("tasks.html", tasks=tsks)


@app.route("/add_tasks", methods=["POST", "GET"])
def add_tasks():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        tr = TaskRepository(username=session['username'])
        tr.add_task(title=title, description=description)
        flash("Task added successfully")
        return redirect(url_for("tasks"))
    else:
        return render_template("task.html")


@app.route("/edit_task/<id>", methods=["POST", "GET"])
def edit_task(id):
    tr = TaskRepository(username=session['username'])
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        done = 'done' in request.form
        if done:
            tr.edit_task(id=id, title=title, description=description, done=done)
        else:
            tr.edit_task(id=id, title=title, description=description, done=done)
        flash("Task updated successfully")
        return redirect(url_for("tasks"))
    else:
        t = tr.find_by_id(id)
        return render_template("task.html", editmode=True, task=t, id=id)


@app.route("/delete_task/<id>", methods=["GET"])
def delete_task(id):
    tr = TaskRepository(username=session['username'])
    tr.delete_task(id)
    return redirect(url_for("tasks"))


@app.route("/about")
def about():
    return "This app is about tasks"
