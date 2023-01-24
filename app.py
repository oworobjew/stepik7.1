from flask import Flask, jsonify, request
app = Flask(__name__)
from neo4j import GraphDatabase
driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "testtest"), database="neo4j")


# --------------------------------- EMPLOYEES

# GET EMPLOYEES - curl -X GET http://localhost:5000/employees?filterby=name&filterphrase=an&sortby=name
def GetEmployees(tx, sortby = '', filterby = '', filterphrase = ''):
    query = "match (n:Employee) return n"

    if (filterby == 'name'):
        query = f"match (n:Employee) where toLower(n.name) contains toLower('{filterphrase}') return n"
    elif (filterby == 'last_name'):
        query = f"match (n:Employee) where toLower(n.last_name) contains toLower('{filterphrase}') return n"
    elif (filterby == 'job'):
        query = f"match (n:Employee) where toLower(n.job contains) toLower('{filterphrase}') return n"

    if (sortby == 'name'):
        query = query + " order by n.name"
    elif (sortby == 'last_name'):
        query = query + " order by n.last_name"
    elif (sortby == 'job'):
        query = query + " order by n.job"
    
    res = tx.run(query).data()
    workers = [{'name': res['n']['name'],'last_name': res['n']['last_name'],'job': res['n']['job']} for res in res]
    return jsonify(workers)

@app.route('/employees', methods=['GET'])
def GetEmployeesRoute():
    #print(request.args.get('sortby'),request.args.get('filterby'),request.args.get('filterphrase'))
    with driver.session() as session:
        res = session.execute_read(GetEmployees,request.args.get('sortby'),request.args.get('filterby'),request.args.get('filterphrase'))
        return res


# ADD EMPLOYEE - curl -X POST -d "name=Maiev&last_name=Shadowsong&job=Warden&department=Darnassus" http://localhost:5000/employees
def AddEmployee(tx, empname, emplastname, empjob, empdepartment):
    checkemployee = f"match (n:Employee {{name: '{empname}', last_name: '{emplastname}', job: '{empjob}'}}) return n"
    checkdepartment = f"match (n:Department {{name: '{empdepartment}'}}) return n"
    employeeexists = tx.run(checkemployee).data()
    departmentexists = tx.run(checkdepartment).data()

    if not employeeexists and departmentexists:
        query = f"create (n:Employee {{name:'{empname}', last_name:'{emplastname}', job:'{empjob}'}}) with n match (d:Department {{name:'{empdepartment}'}}) with n,d create (n)-[r:WORKS_IN]->(d)"
        tx.run(query)
        return 'Added employee!'
    elif employeeexists:
        return 'This employee already exists!'
    elif not departmentexists:
        return 'This department does not exist!'


@app.route('/employees', methods=['POST'])
def AddEmployeeRoute():
    name = request.form.get('name')
    last_name = request.form.get('last_name')
    job = request.form.get('job')
    department = request.form.get('department')
    #print(name,last_name,job,department)
    if not name or not last_name or not job or not department:
        res = 'Missing information!'
        return res
    with driver.session() as session:
        res = session.execute_write(AddEmployee, name, last_name, job, department)
        return res 


# UPDATE EMPLOYEE - curl -X PUT -d "job=Speaker" http://localhost:5000/employees/77
def UpdateEmployee(tx, id, newname, newlastname, newjob, newdepartment):
    findquery = f"match (n:Employee)-[:WORKS_IN]->(d:Department) WHERE id(n) = {id} return n,d"
    data = tx.run(findquery).data()
    name = newname or data[0]['n']['name']
    last_name = newlastname or data[0]['n']['last_name']
    job = newjob or data[0]['n']['job']
    department = newdepartment or data[0]['d']['name']
    print(id,name,last_name,job,department)
    
    if data:
        updatequery = f"match (n:Employee {{name: '{data[0]['n']['name']}', last_name: '{data[0]['n']['last_name']}', job: '{data[0]['n']['job']}'}})-[r:WORKS_IN]->(d:Department {{name:'{data[0]['d']['name']}'}}) set n.name='{name}', n.last_name='{last_name}', n.job='{job}' with n,d,r delete r with n match (d2:Department {{name:'{department}'}}) create (n)-[:WORKS_IN]->(d2)"
        tx.run(updatequery)
        return 'Updated employee!'
    else:
        return 'Could not find employee with this id!'

@app.route('/employees/<int:id>', methods=['PUT'])
def UpdateEmployeeRoute(id):
    name = request.form.get('name')
    last_name = request.form.get('last_name')
    job = request.form.get('job')
    department = request.form.get('department')

    with driver.session() as session:
        res = session.write_transaction(UpdateEmployee, id, name, last_name, job, department)
        return res


# DELETE EMPLOYEE - curl -X DELETE http://localhost:5000/employees/77
def DeleteEmployee(tx, id):
    findquery = f"match (n:Employee)-[r]->(d:Department) where id(n) = {id} return d"
    data = tx.run(findquery).data()
    department = data[0]['d']['name']

    if data:
        deletequery = f"match (n:Employee) where id(n)={id} detach delete n"
        tx.run(deletequery)
        findanotheremployeequery= f"match (n:Employee)-[:WORKS_IN]->(d:Department) where d.name = '{department}' return n"
        anotheremployeeexists = tx.run(findanotheremployeequery).data()
        #print(anotheremployeeexists)
        if not anotheremployeeexists:
            deletedepartmentquery = f"match (d:Department) where d.name = '{department}' detach delete d"
            tx.run(deletedepartmentquery)
            return 'Deleted employee and their department!'
        return 'Deleted employee!'
    else:
        return 'Could not find employee with this id!'

@app.route('/employees/<int:id>', methods=['DELETE'])
def DeleteEmployeeRoute(id):
    with driver.session() as session:
        res = session.write_transaction(DeleteEmployee, id)
        return res


# GET EMPLOYEE SUBORDINATES - curl -X GET http://localhost:5000/employees/73/subordinates
def GetSubordinates(tx, id):
    query = f"match (n:Employee where id(n)={id})-[:MANAGES]->(n2:Employee) return n2"
    res = tx.run(query).data()
    
    if res:
        subordinates = [{'name': r['n2']['name'],'last_name': r['n2']['last_name'],'job': r['n2']['job']} for r in res]
        return jsonify(subordinates)
    else:
        return 'No subordinates'

@app.route('/employees/<int:id>/subordinates', methods=['GET'])
def GetSubordinatesRoute(id):
    with driver.session() as session:
        res = session.execute_read(GetSubordinates, id)
        return res


# GET EMPLOYEE DEPARTMENT - curl -X GET http://localhost:5000/employees/73/department
def GetEmployeeDepartment(tx, id):
    query = f"match (n:Employee where id(n)={id})-[:WORKS_IN]->(d:Department)<-[:WORKS_IN]-(n2:Employee) return d, count(n2)+1 as c"
    res = tx.run(query).data()
    
    if res:
        departmentinfo = {'name': res[0]['d']['name'],'employee count':res[0]['c']}
        return jsonify(departmentinfo)
    else:
        return 'No subordinates found!'

@app.route('/employees/<int:id>/department', methods=['GET'])
def GetEmployeeDepartmentRoute(id):
    with driver.session() as session:
        res = session.execute_read(GetEmployeeDepartment, id)
        return res


# --------------------------------- DEPARTMENTS

# GET DEPARTMENTS - curl -X GET http://localhost:5000/departments?filterby=name&filterphrase=an&sortby=count
def GetDepartments(tx, sortby = '', filterphrase = ''):
    query = f"match (n:Employee)-[:WORKS_IN]->(d:Department) return d, count(n) as count"

    if (filterphrase):
        query = f"match (n:Employee)-[:WORKS_IN]->(d:Department) where toLower(d.name) contains toLower('{filterphrase}') return d, count(n) as count"

    if (sortby == 'name'):
        query = query + " order by d.name"
    elif (sortby == 'count'):
        query = query + " order by count"
    
    res = tx.run(query).data()
    if res:
        departmentinfo = [{'name': r['d']['name'],'employee count':r['count']} for r in res]
        return jsonify(departmentinfo)
    else:
        return 'No departments found!'

@app.route('/departments', methods=['GET'])
def GetDepartmentsRoute():
    with driver.session() as session:
        res = session.execute_read(GetDepartments,request.args.get('sortby'),request.args.get('filterphrase'))
        return res


# GET DEPARTMENT EMPLOYEES - curl -X GET http://localhost:5000/departments/87/employees
def GetDepartmentEmployees(tx, id):
    query = f"match (n:Employee)-[:WORKS_IN]->(d:Department where id(d)={id}) return n"
    res = tx.run(query).data()
    if res:
        workers = [{'name': r['n']['name'],'last_name': r['n']['last_name'],'job': r['n']['job']} for r in res]
        return jsonify(workers)
    else:
        return 'No workers found!'

@app.route('/departments/<int:id>/employees', methods=['GET'])
def GetDepartmentEmployeesRoute(id):
    with driver.session() as session:
        res = session.execute_read(GetDepartmentEmployees, id)
        return res






if __name__ == '__main__':
    app.run()

