from flask import Flask, render_template, redirect, url_for, session, request, jsonify, flash
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import timedelta, timezone, datetime
import os
import pyotp
import qrcode
import hashlib
import json
import random
from flask_apscheduler import APScheduler 
import requests

basedir = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = basedir+'\public\image'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

app = Flask(
    __name__,
    static_folder='public',
    static_url_path='/'
)  # 建立 application 物件


app.secret_key = os.urandom(24)
app.permanent_session_lifetime = timedelta(minutes=60)
app.config['SECRET_KEY'] = os.urandom(24)


connection_string = 'mongodb+srv://samsonm825:g4zo1j6y94@cluster0.ow4o5g4.mongodb.net/?retryWrites=true&w=majority'
client = MongoClient(connection_string)
dbs = client.bittop

key = 'iLufaMySuperSecretKey'
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()



@app.route('/admin_manifestOrder', methods=['GET', 'POST'])
def admin_manifestOrder():
  if 'id' in session and session['display_name'] == '最高管理者':
    orderNo_data = []
    page_data = {}
    order_data = []
    match = {}
    match_data = {}

    if request.method == 'POST':
      # 條件判斷
      oId = request.form['no']
      name = request.form['name']
      if oId != '':
        match['orderNo'] = {'$regex': oId}
      if name != '':
        match['name'] = name

    if request.args.get('methods') == 'setorderno':
      oid = request.args.get('oid')
      orderNo = request.args.get('orderno')
      match_no = request.args.get('match_no')
      match_name = request.args.get('match_name')
      if match_no != "":
        match['orderNo'] = {'$regex': match_no}
      if match_name != "":
        match['name'] = match_name
      order_data_temp = dbs.jeg_order.find_one(
        {
          "_id": ObjectId(oid)
        }
      )

      dbs.jeg_order.update_one(
        {
          "_id": ObjectId(oid)
        },
        {
          "$set": {
            "order_detail": ObjectId(orderNo)
          }
        }
      )

      dbs.order_no.update_one(
        {
          "_id": ObjectId(orderNo)
        },
        {
          "$set": {
            "is_used": True
          },
          "$push": {
            "used_oid": order_data_temp['bankAccount']
          }
        }
      )
      if match_no == 'undefined' and match_name == 'undefined':
        return redirect('admin_manifestOrder')

    current_page = request.args.get('page')
    skip = 0
    per = 20
    if current_page != None:
      skip = per * (int(current_page) - 1)
    else:
      current_page = 1

    # 判斷條件時要加入 篩選條件
    order_len = dbs.jeg_order.count_documents(match)
    if order_len % per == 0:
      all_page = order_len // per
    else:
      all_page = (order_len // per) + 1
    page_data['all_page'] = all_page
    page_data['current_page'] = current_page
    #分頁處理結束

    if 'name' in match or 'orderNo' in match:
      skip = 0
      per = 10000
      page_data = {}


    temp_data = dbs.jeg_order.find(match).limit(per).skip(skip)
    for doc in temp_data:
      doc['_id'] = str(doc['_id'])
      doc['uid'] = str(doc['uid'])
      if 'order_detail' not in doc:
        doc['order_detail'] = False
      order_data.append(doc)
    
    if 'orderNo' in match  and 'name' in match:
      match_data = {
        "no": match['orderNo']['$regex'],
        "name": match['name']
      }
    elif 'orderNo' in match and 'name' not in match:
      match_data = {
        "no": match['orderNo']['$regex'],
        "name": ""
      }
    elif 'name' in match and 'orderNo' not in match:
      match_data = {
        "no": "",
        "name": match['name']
      }
    print(match)
    return render_template('admin_manifestOrder.html', order_data=order_data, page_data=page_data, match_data=match_data)
  else:
    return redirect('admin_login')
@app.route('/admin_manifestUser', methods=['GET', 'POST'])
def admin_manifestUser():
    if 'id' in session and session['display_name'] == '最高管理者':
        user_data = []
        if request.method == "POST":
            if request.form['name'] == '' or request.form['account'] == '' or request.form['password'] == '':
                flash('栏位不能有空值 请重新填写后送出')
                return redirect("admin_manifestUser")       
            if request.form['id'] !="":
                dbs.jeg_user.update_one(
                    {
                        "_id":ObjectId(request.form['id'])
                    },
                    {
                        "$set":{
                            "name":request.form['name'],
                            "account":request.form['account'],
                            "password":request.form['password'],
                        }
                    }
                )
            else:
                user = dbs.jeg_user.find_one(
                    {
                        "account":request.form['account'],
                    }
                )
                if user == None:
                    dbs.jeg_user.insert_one(
                    {
                        "name":request.form['name'],
                        "account":request.form['account'],
                        "password":request.form['password'],
                    }                    
                )
                else:
                    flash('账号重复注册 请确认之后重新新增')

            return redirect("admin_manifestUser")  
        else:
            if request.args.get('methods') == 'delete':
                dbs.jeg_user.delete_one(
                    {
                        "_id": ObjectId(request.args.get('id'))
                    }
                )
                return redirect("admin_manifestUser") 
            temp_data = dbs.jeg_user.find()
            for doc in temp_data:
                doc["_id"] = str(doc["_id"])
                user_data.append(doc)

            return render_template('admin_manifestUser.html', user_data=user_data)
    else:
        return redirect('admin_login') 

@scheduler.task('interval', id='do_job_1', max_instances=100, misfire_grace_time=60, minutes=60)
def job1():
    product_data = []
    member_data = []
    product_find = dbs.product.find(
        {
            'is_buy': False
        }
    )
    for doc in product_find:
        product_data.append(doc)

    member_find = dbs.member.find(
        {
            'is_verify': 1,
            'status': True
        }
    )
    for doc in member_find:
        member_data.append(doc)

    random.shuffle(member_data)

    for pindex, product in enumerate(product_data):
        for mindex, member in enumerate(member_data):
            if member['coin'] >= product['price']:
                dbs.order.insert_one({
                    'product_id': ObjectId(product['_id']),
                    'mid': ObjectId(member['_id']),
                    'is_paid': False,
                    'prove_img': '',
                    'status': False,
                    'factory_id': ''
                })

                order_data = dbs.order.find_one({ 'product_id': ObjectId(product['_id'])})
                member_data = dbs.member.find_one({ "_id":ObjectId(member['_id']) })
                product_data = dbs.product.find_one({"_id":ObjectId(product['_id'])})

                payload = {
                    'oId': str(order_data['_id']),
                    'p_name': product_data['name'],
                    'bank_account': member_data['bankAccount']
                }

                res = requests.post('http://127.0.0.1:5001/api/v1/send_order', json=payload)
                res_data = res.json()

                dbs.order.update_one(
                    {
                        '_id': ObjectId(order_data['_id'])
                    },
                    {
                        '$set': {
                            'factory_id': res_data['data']['factory_id']
                        }
                    }
                )
                dbs.member.update_one(
                    {
                        '_id': ObjectId(member['_id'])
                    },
                    {
                        '$set': {
                            'coin': member['coin'] - product['price'],
                            'status': False
                        }
                    }
                )
                dbs.product.update_one(
                    {
                        '_id': ObjectId(product['_id'])
                    },
                    {
                        '$set': {
                            'is_buy': True
                        }
                    }
                )
                member_data.pop(mindex)
# 将资料转换成json存入资料库
# jsonFile = open('example.json','r',encoding='UTF-8')
# jsonF = json.load(jsonFile)
# i = 1
# for doc in jsonF:
#     data = {
#         'name':doc['姓名'],
#         'phone':'0' + str(doc['电话']),
#         'address':doc['地址'].replace('\t', ''),
#         'number':i
#     }
#     i =  i + 1
#     dbs.fake_data.insert_one(data)


def verify_potp(potp):
    totp = pyotp.TOTP(key)
    result = totp.verify(potp)
    return result


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def random_number(count):
    number_list = []
    for i in range(999):
        number_list.append(i)
    random.shuffle(number_list)
    return number_list[0:count]


# @app.route('/', methods=['GET', 'POST'])
# def index():
#     if request.method == 'POST':
#         member_data = []
#         account = request.form['account']
#         password = request.form['password']
#         potp = request.form['potp']
#         session['account'] = account

#         pottp_resul = verify_potp(potp)

#         member_find = dbs.bittop_member.find({
#             'account': account
#         })
#         for doc in member_find:
#             member_data.append(doc)
#         if len(member_data) <= 0:
#             return redirect('index')
#         password_str = password + member_data[0]['salt']
#         user_password = hashlib.sha1(password_str.encode('utf-8'))

#         if member_data[0]['password'] == user_password.hexdigest():
#             session.permanent = True
#             session['display_name'] = member_data[0]['display_name']
#             session['id'] = str(member_data[0]['_id'])
#             return redirect('member_dashboard')
#         else:
#             return redirect('index.html')
#     else:
#         if 'display_name' in session:
#             return redirect('member_dashboard')
#         return render_template('index.html')

@app.route('/', methods=['GET', 'PSOT'])
def index():
    return render_template('index.html')



@app.route('/member_usdt', methods=['GET', 'POST'])
def member_usdt():
    if 'display_name' in session :
        if request.method == 'GET':
            if request.args.get('method') == 'success':
                dbs.member_usdt.update_one(
                    {
                        '_id': ObjectId(request.args.get('bId'))
                    },
                    {
                        '$set':{
                            'status': True
                        }
                    }           
                )
            elif request.args.get('method') == 'falid':
                member_usdt = dbs.member_usdt.find_one({ '_id': ObjectId(request.args.get('bId')) })
                member_data = dbs.member.find_one({ 'account': member_usdt['m_account'] })
                dbs.member.update_one(
                    {
                        '_id': ObjectId(member_data['_id'])
                    },
                    {
                        '$set':{
                            'bonus': member_data['bonus'] + float(bonus_data['pay_bonus'])
                        }
                    }
                )
                dbs.bonus_order.delete_one({ '_id': ObjectId(request.args.get('bId')) })


            bonus_data = []
            bonus_find = dbs.bonus_order.find({})
            for doc in bonus_find:
                bonus_data.append(doc)
            return render_template('admin_bonus.html', bonus_data=bonus_data)
    elif 'id' in session and request.method == 'POST':
        member_data = dbs.member.find_one({ '_id': ObjectId(session['id']) })
        bonus_count = request.form['bonus']
        if float(bonus_count) > member_data['bonus']:
            return redirect('profile')
        else:
            data = {
                'm_name': member_data['name'],
                'm_account': member_data['account'],
                'm-bonus': member_data['bonus'] - float(bonus_count),
                'pay_bonus': float(bonus_count),
                'status': False
            }
            dbs.bonus_order.insert_one(data)

            dbs.member.update_one(
                {
                    '_id': ObjectId(session['id'])
                },
                {
                    '$set':{
                        'bonus':member_data['bonus'] - float(bonus_count)
                    }
                }
            )
            return redirect('profile')
    else:
        return redirect('admin_login')



@app.route('/admin_bonus', methods=['GET', 'POST'])
def admin_bonus():
    if 'display_name' in session and session['display_name'] == '最高管理者':
        if request.method == 'GET':
            if request.args.get('method') == 'success':
                dbs.bonus_order.update_one(
                    {
                        '_id': ObjectId(request.args.get('bId'))
                    },
                    {
                        '$set':{
                            'status': True
                        }
                    }           
                )
            elif request.args.get('method') == 'falid':
                bonus_data = dbs.bonus_order.find_one({ '_id': ObjectId(request.args.get('bId')) })
                member_data = dbs.member.find_one({ 'account': bonus_data['m_account'] })
                dbs.member.update_one(
                    {
                        '_id': ObjectId(member_data['_id'])
                    },
                    {
                        '$set':{
                            'bonus': member_data['bonus'] + float(bonus_data['pay_bonus'])
                        }
                    }
                )
                dbs.bonus_order.delete_one({ '_id': ObjectId(request.args.get('bId')) })


            bonus_data = []
            bonus_find = dbs.bonus_order.find({})
            for doc in bonus_find:
                bonus_data.append(doc)
            return render_template('admin_bonus.html', bonus_data=bonus_data)
    elif 'id' in session and request.method == 'POST':
        member_data = dbs.member.find_one({ '_id': ObjectId(session['id']) })
        bonus_count = request.form['bonus']
        if float(bonus_count) > member_data['bonus']:
            return redirect('profile')
        else:
            data = {
                'm_name': member_data['name'],
                'm_account': member_data['account'],
                'm-bonus': member_data['bonus'] - float(bonus_count),
                'pay_bonus': float(bonus_count),
                'status': False
            }
            dbs.bonus_order.insert_one(data)

            dbs.member.update_one(
                {
                    '_id': ObjectId(session['id'])
                },
                {
                    '$set':{
                        'bonus':member_data['bonus'] - float(bonus_count)
                    }
                }
            )
            return redirect('profile')
    else:
        return redirect('admin_login')



@app.route('/admin_log', methods=['GET', 'POST'])
def admin_log():
    if 'display_name' in session and session['display_name'] == '最高管理者':
        record_data = []
        record_find = dbs.log_record.find({})
        for doc in record_find:
            record_data.append(doc)
        return render_template('admin_log.html', record_data=record_data)
    else:
        return redirect('admin_login')


@app.route('/resetPassword', methods=['GET', 'POST'])
def resetPassword():
    if 'id' in session:
        if request.method == 'POST':
            old_password = request.form['oldPassword']
            password = request.form['password']
            repeat_password = request.form['repeatPassword']
            member_data = dbs.member.find_one({'_id': ObjectId(session['id'])})
            old_password_str = old_password + member_data['salt']
            old_password = hashlib.sha1(old_password_str.encode('utf-8'))

            if member_data['password'] == old_password.hexdigest() and password == repeat_password:
                password_str = password + member_data['salt']
                user_password = hashlib.sha1(password_str.encode('utf-8'))
                dbs.member.update_one(
                    {
                        '_id': ObjectId(session['id'])
                    },
                    {
                        '$set': {
                            'password': user_password.hexdigest()
                        }
                    }
                )
                session.clear()
                return redirect('login')

            else:
                return redirect('resetPassword')
        else:

            return render_template('resetPassword.html')
    else:
        return redirect('login')
    


@app.route('/cart/<product>')
def cart(product):
    if 'id' in session:
        member_data = dbs.member.find_one({'_id': ObjectId(session['id'])})

        if product == 'all':
            product_data = []
            product_find = dbs.product.find(
                {
                    'is_buy': False,
                    'price': {
                        '$lte': member_data['coin']
                    }
                }
            )
            for doc in product_find:
                product_data.append(doc)

            return render_template('cart.html', product_data=product_data)
        else:
            product_data = dbs.product.find_one({'_id': ObjectId(product)})
            if request.args.get('methods') == 'buy':
                if request.args.get('mid') != session['id']:
                    session.clear()
                    return redirect(url_for('login'))
                dbs.member.update_one(
                    {
                        '_id': ObjectId(request.args.get('mid'))
                    },

                    {
                        '$set': {
                            'coin': member_data['coin']-product_data['price']
                        }

                    })
                dbs.product.update_one(
                    {
                        '_id': ObjectId(product)
                    },

                    {
                        '$set': {
                            'is_buy': True
                        }

                    })
                dbs.order.insert_one(
                    {
                        'product_id': ObjectId(product),
                        'mid': ObjectId(request.args.get('mid')),
                        'is_paid': False,
                        'prove_img': '',
                        'status': False
                    }
                )

                order_data = dbs.order.find_one({ 'product_id': ObjectId(product)})
                member_data = dbs.member.find_one({ "_id":ObjectId(request.args.get('mid')) })
                product_data = dbs.product.find_one({"_id":ObjectId(product)})

                payload = {
                    'oId': str(order_data['_id']),
                    'p_name': product_data['name'],
                    'bank_account': member_data['bankAccount']
                }

                res = requests.post('http://127.0.0.1:5001/api/v1/send_order', json=payload)
                res_data = res.json()

                dbs.order.update_one(
                    {
                        '_id': ObjectId(order_data['_id'])
                    },
                    {
                        '$set': {
                            'factory_id': res_data['data']['factory_id']
                        }
                    }
                )






                return redirect(url_for('cart', product='all'))
            else:
                return render_template('cart_order.html', product_data=product_data, member_data=member_data)

    else:
        return redirect(url_for('login'))


@app.route('/admin_user', methods=['GET', 'POST'])
def admin_user():
    if 'display_name' in session and session['display_name'] == '最高管理者':
        if request.method == 'POST':
            name = request.form['name']
            account = request.form['account']
            id = request.form['id']
            password = request.form['password']
            display_name = request.form['display_name']

            if id == '':
                user_data = dbs.admin.find_one({'account': account})
                if user_data != None:
                    return redirect('admin_user')
                salt = 'KKJNWSDJIJDJIWWIDJ'
                password_str = password + salt
                user_password = hashlib.sha1(password_str.encode('utf-8'))
                dbs.admin.insert_one({
                    'name': name,
                    'account': account,
                    'password': user_password.hexdigest(),
                    'salt': salt,
                    'display_name': display_name
                })
                return redirect('admin_user')
            else:
                user_data = dbs.admin.find_one({'_id': ObjectId(id)})
                if user_data['password'] != password:
                    password_str = password + user_data['salt']
                    user_password = hashlib.sha1(password_str.encode('utf-8'))
                    password = user_password.hexdigest()
                dbs.admin.update_one(
                    {
                        '_id': ObjectId(id)
                    },
                    {
                        '$set': {
                            'name': name,
                            'password': password,
                            'display_name': display_name

                        }
                    })
                return redirect('admin_user')
        else:
            if request.args.get('methods') == 'delete':
                dbs.admin.delete_one({"_id": ObjectId(request.args.get('id'))})
            user_data = []
            user_find = dbs.admin.find()
            for doc in user_find:
                doc['_id'] = str(doc['_id'])
                user_data.append(doc)
            return render_template('admin_user.html', user_data=user_data)
    else:
        return redirect('admin_dashboard')


@app.route('/admin_order',methods=['GET','POST'])
def admin_order():
    if 'display_name' and session['display_name'] == '最高管理者':
        match = {}
        page_data = {}
        orderNo_data = []
        print(request.method)
        if request.method =='POST':
            oId = request.form['no']
            is_paid = request.form['is_paid']
            name = request.form['name']
            
            if is_paid =='0' and is_paid != '':
                is_paid = False
            elif is_paid == '1' and is_paid !='':
                is_paid = True

            if oId != '':
                match['_id'] = ObjectId(oId)
            elif is_paid != '':
                match['is_paid'] = is_paid
            elif name != '':
                match['name'] = name

        if request.args.get('methods') == 'post':
            order_data = dbs.order.find_one(
                {
                    '_id': ObjectId(request.args.get('oid'))
                }
            )
            if order_data == None:
                session.clear()
                return redirect('admin_login')
            product_data = dbs.product.find_one(
                {'_id': ObjectId(order_data['product_id'])})
            member_data = dbs.member.find_one(
                {'_id': ObjectId(order_data['mid'])})

            dbs.member.update_one(
                {
                    '_id': ObjectId(member_data['_id'])
                },
                {
                    '$set': {
                        'real_coin': member_data['real_coin'] + int(product_data['price'])
                    }
                }
            )
            dbs.order.update_one(
                {
                    '_id': ObjectId(request.args.get('oid'))
                },
                {
                    '$set': {
                        'is_paid': True
                    }
                }
            )

            record_data = {
                'm_name': member_data['name'],
                'oId': str(order_data['_id']),
                'in_coin':  product_data['price'],
                'out_coin': 0,
                'in_bonus': 0,
                'out_bonus': 0
            }

            dbs.log_record.insert_one(record_data)

        elif request.args.get('methods') == 'delete':
            order_data = dbs.order.find_one(
                {
                    '_id': ObjectId(request.args.get('oid'))
                }
            )
            if order_data == None:
                session.clear()
                return redirect('admin_login')
            dbs.order.delete_one(
                {
                    '_id': ObjectId(request.args.get('oid'))
                }
            )

        elif request.args.get('methods') == 'setorderno':
            oid = request.args.get('oid')
            orderNo = request.args.get('orderno')
            order_data = dbs.order.find_one(
                {
                    "_id": ObjectId(oid)
                }
            )
            member_data = dbs.member.find_one(
                {
                    "_id": ObjectId(order_data['mid'])
                }
            )
            dbs.order.update_one(
                {
                    "_id": ObjectId(oid)
                },
                {
                    "$set": {
                        "order_detail": ObjectId(orderNo)
                    }
                }
            )
            print(orderNo)
            dbs.order_no.update_one(
                {
                    "_id": ObjectId(orderNo)
                },
                {
                    "$set": {
                        "is_used": True
                    },
                    "$push": {
                        "used_oid": member_data['bankAccount']
                    }
                }
            )
            return redirect('admin_order')

        current_page = request.args.get('page')
        skip = 0
        per = 4
        if current_page != None:
            skip = per * (int(current_page)-1)
        else:
            current_page = 1

        order_data = []
        order_len = dbs.order.count_documents(match)        
        if order_len % per == 0:
            all_page = order_len // per
        else:
            all_page = (order_len // per) + 1
        page_data['all_page'] = all_page
        page_data['current_page'] = current_page
        
        if 'is_paid' in match or 'name' in match:
            skip = 0
            per = 10000
            page_data = {}
       
        order_find = dbs.order.aggregate([
            {
                '$lookup': {
                    'from': 'product',
                    'localField': 'product_id',
                    'foreignField': '_id',
                    'as': 'product'
                }
            },
            {
                '$lookup': {
                    'from': 'member',
                    'localField': 'mid',
                    'foreignField': '_id',
                    'as': 'member'
                }
            },
            {
                '$match':match
            },
            {
                '$skip': skip
            },
            {
                '$limit': per
            }

        ])
        orderNo_find = dbs.order_no.find()
        for doc in orderNo_find:
            doc['_id'] = str(doc['_id'])
            if 'is_used' not in doc:
                orderNo_data.append(doc)

        for doc in order_find:
            doc['_id'] = str(doc['_id'])
            if 'order_detail' not in doc:
                doc['order_detail'] = False
            order_data.append(doc)

        return render_template('admin_order.html', order_data=order_data, page_data=page_data,
                               orderNo_data=orderNo_data )
    else:
        return redirect('admin_login')


@app.route('/admin_verify', methods=['GET', 'PSOT'])
def admin_verify():
    if 'display_name' and session['display_name'] == '最高管理者':
        if request.args.get('id'):
            if request.args.get('is_verify') == '1':
                dbs.bittop_member.update_one(
                    {
                        '_id': ObjectId(request.args.get('id'))
                    },
                    {
                        '$set': {
                            'is_verify': 1
                        }
                    }
                )
            else:
                dbs.bittop_member.update_one(
                    {
                        '_id': ObjectId(request.args.get('id'))
                    },
                    {
                        '$set': {
                            'is_verify': 2
                        }
                    }
                )

            return redirect('admin_verify')

        member_data = []
        member_find = dbs.bittop_member.find({
            'is_verify': 0
        })

        for doc in member_find:
            member_data.append(doc)

        return render_template('admin_verify.html', member_data=member_data)

    else:
        return redirect('admin_login')


@app.route('/admin_member', methods=['POST', 'GET'])
def admin_member():
    if 'display_name' and session['display_name'] == '最高管理者':
        if request.method == 'POST':
            real_coin = request.form['real_coin']
            bonus = request.form['bonus']
            bonus_rate = request.form['bonus_rate']
            name = request.form['name']
            coin = int(request.form['coin'])
            id = request.form['id']
            bankAccount = request.form['bankAccount']

            dbs.member.update_one(
                {
                    '_id': ObjectId(id)
                },
                {
                    '$set': {
                        'name': name,
                        'coin': coin,
                        'bankAccount': bankAccount,
                        'real_coin': int(real_coin),
                        'bonus': float(bonus),
                        'bonus_rate': float(bonus_rate)
                    }
                }
            )
            return redirect('admin_member')

        else:
            if request.args.get('methods') == 'delete':
                dbs.member.delete_one(
                    {
                        '_id': ObjectId(request.args.get('id'))
                    }
                )
            current_page = request.args.get('page')
            skip = 0
            per = 4
            if current_page != None:
                skip = per * (int(current_page)-1)
            else:
                current_page = 1
            member_data = []
            member_len = dbs.member.count_documents({})

            page_data = {}
            if member_len % per == 0:
                all_page = member_len // per
            else:
                all_page = (member_len // per) + 1
            page_data['all_page'] = all_page
            page_data['current_page'] = current_page
            
            member_find = dbs.member.find(
               {
                    'is_verify': 1
                },
               {
                    'password': 0,
                    'status': 0
                }
               )
            for doc in member_find:
                doc['_id'] = str(doc['_id'])
                member_data.append(doc)

            return render_template("admin_member.html", member_data=member_data,page_data=page_data)

    else:
        return redirect('admin_login')


@app.route('/admin_dashboard',methods=['GET', 'POST'])
def admin_dashboard():
    if 'display_name' in session:
        return render_template('admin_dashboard.html')
    else:
        return redirect('admin_login')
    

# @app.route('/member_dashboard',methods=['GET', 'POST'])
# def member_dashboard():
#     if 'display_name' in session:
#         return render_template('member_dashboard.html')
#     else:
#         return redirect('index')



@app.route('/order')
def order():
    if 'id' in session:
        if request.args.get('method') == 'success':
            oId = request.args.get('oId')
            pId = request.args.get('pId')
            product_data = dbs.product.find_one({
                '_id': ObjectId(pId),
            })
            order_data = dbs.order.find_one({
                '_id': ObjectId(oId),
            })
            if order_data == None or product_data == None:
                return redirect('order')
            member_data = dbs.member.find_one({
                '_id': ObjectId(session['id']),
            })

            record_data = {
                'm_name': member_data['name'],
                'oId': oId,
                'in_coin': 0,
                'out_coin': product_data['price'],
                'in_bonus': float(product_data['price'])*0.002,
                'out_bonus': 0
            }
            dbs.member.update_one(
                {
                    '_id': ObjectId(session['id']),
                },
                {
                    '$set': {
                        'bonus': member_data['bonus'] + float(product_data['price'])*0.002,
                        'real_coin': member_data['real_coin'] - product_data['price'],
                        'coin': member_data['coin'] + product_data['price']
                    }
                }
            )
            dbs.log_record.insert_one(record_data)
            dbs.order.update_one(
                {
                    '_id': ObjectId(oId)
                },
                {
                    '$set': {
                        'status': True
                    }
                }
            )
            return redirect('order')

        order_data = []
        order_find = dbs.order.aggregate([
            {
                '$match': {
                    'mid': ObjectId(session['id'])
                }
            },
            {
                '$lookup': {
                    'from': 'product',
                    'localField': 'product_id',
                    'foreignField': '_id',
                    'as': 'product'
                }
            }
        ])

        for doc in order_find:
            order_data.append(doc)
        return render_template('order.html', order_data=order_data)
    else:
        return redirect('login')
    
@app.route('/admin_base', methods=['GET', 'POST'])
def admin_base():
    if 'account' in session :
        # 直接从会话中获取账号
        account = session.get('account', 'DefaultAccount')
        return render_template('admin_base.html', account="account")

    else:
        return redirect('admin_base')


@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        admin_data = []
        account = request.form['account']
        password = request.form['password']
        potp = request.form['potp']
        session['account'] = account

        pottp_resul = verify_potp(potp)

        admin_find = dbs.bittop_admin.find({
            'account': account
        })
        for doc in admin_find:
            admin_data.append(doc)
        if len(admin_data) <= 0:
            return redirect('admin_login')
        password_str = password + admin_data[0]['salt']
        user_password = hashlib.sha1(password_str.encode('utf-8'))

        if admin_data[0]['password'] == user_password.hexdigest():
            session.permanent = True
            session['display_name'] = admin_data[0]['display_name']
            session['id'] = str(admin_data[0]['_id'])
            return redirect('admin_dashboard')
        else:
            return redirect('admin_login')
    else:
        if 'display_name' in session:
            return redirect('admin_dashboard')
        return render_template('admin_login.html')


@app.route('/admin_logout')
def admin_logout():
    session.clear()
    return redirect('admin_login')
@app.route('/member_logout')
def member_logout():
    session.clear()
    return redirect('/')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        member_data = []
        account = request.form["account"]
        password = request.form["password"]
        session['account'] = account

        member_find = dbs.bittop_member.find({
            'account': account
        })

        for doc in member_find:
            member_data.append(doc)

        if len(member_data) <= 0:
            return redirect('login')

        password_str = password + member_data[0]['salt']
        user_password = hashlib.sha1(password_str.encode('utf-8'))

        if member_data[0]['password'] == user_password.hexdigest() and member_data[0]['is_verify'] == 1:
            session.permanent = True
            session['name'] = member_data[0]['name']
            session['id'] = str(member_data[0]['_id'])

            return redirect('member_dashboard')
        else:
            return redirect('login')

    else:
        if 'id' in session:
            return redirect('member_dashboard')
        return render_template('login.html')


@app.route('/admin_product', methods=['GET', 'POST'])
def admin_product():
    if 'display_name' in session:
        if request.method == 'POST':
            potp = request.form['potp']
            potp_result = verify_potp(potp)
            potp_result = True
            if potp_result == True:
                name = request.form['name']
                price = request.form['price']
                desc = request.form['desc']
                factory_name = request.form['factory_name']
                factory_bank = request.form['factory_bank']

                if request.form['id'] == '':
                    dbs.product.insert_one(
                        {
                            'name': name,
                            'price': price,
                            'desc': desc,
                            'factory_name': factory_name,
                            'factory_bank': factory_bank,
                            'is_buy': False
                        }
                    )
                else:
                    dbs.product.update_one(
                        {
                            '_id': ObjectId(request.form['id'])
                        },
                        {
                            '$set': {
                                'name': name,
                                'price': price,
                                'desc': desc,
                                'factory_name': factory_name,
                                'factory_bank': factory_bank
                            }
                        }
                    )

                return redirect('admin_product')
            else:
                return redirect('admin_product')
        else:
            if request.args.get('methods') == 'delete':
                dbs.product.delete_one(
                    {
                        '_id': ObjectId(request.args.get('id'))
                    }
                )
            product_data = []
            product_find = dbs.product.find()
            for doc in product_find:
                doc['_id'] = str(doc['_id'])
                if doc['is_buy'] == True:
                    doc['is_buy'] = 1
                else:
                    doc['is_buy'] = 0
                product_data.append(doc)
            return render_template('admin_product.html', product_data=product_data)
    else:
        return redirect('admin_login')





@app.route('/order_prove', methods=['POST'])
def order_prove():
    if 'id' in session:
        oId = request.form['oId']
        f = request.files['prove_img']
        mid = session['id']
        member_data = dbs.member.find_one({'_id': ObjectId(mid)})
        account = member_data['account']
        imgUrl = ''

        if f and allowed_file(f.filename):
            file_path = basedir + '\public\image' + f'\{account}'
            if not os.path.isdir(file_path):
                os.mkdir(file_path)
            f.save(os.path.join(file_path, f.filename))
            imgUrl = f'/image/{account}/{f.filename}'

        dbs.order.update_one(
            {
                '_id': ObjectId(oId)
            },
            {
                '$set': {
                    'prove_img': imgUrl
                }
            }
        )

        return redirect('order')
    else:
        return redirect('login')

@app.route('/member_dashboard', methods=['GET', 'POST'])
def member_dashboard():
    if 'id' in session:
        if request.args.get('method') == 'controlStatus':
            if request.args.get('status') == "1":
                status = True
            else:
                status = False
            print(status)
            dbs.member.update_one(
                {
                    '_id': ObjectId(session['id'])
                },
                {
                    '$set': {
                        'status': status
                    }
                }

            )
            temp_data = dbs.member.find_one({'_id': ObjectId(session['id'])})
            print(temp_data)
            return redirect('member_dashboard')

        member_data = dbs.member.find_one(
            {
                '_id': ObjectId(session['id'])
            },
            {
                'password': 0
            }
        )

        return render_template('member_dashboard.html', member_data=member_data)
    else:
        return redirect('login')


# @app.route('/profile', methods=['GET', 'POST'])
# def profile():
#     if 'id' in session:
#         if request.args.get('method') == 'controlStatus':
#             if request.args.get('status') == "1":
#                 status = True
#             else:
#                 status = False
#             print(status)
#             dbs.member.update_one(
#                 {
#                     '_id': ObjectId(session['id'])
#                 },
#                 {
#                     '$set': {
#                         'status': status
#                     }
#                 }

#             )
#             temp_data = dbs.member.find_one({'_id': ObjectId(session['id'])})
#             print(temp_data)
#             return redirect('profile')

#         member_data = dbs.member.find_one(
#             {
#                 '_id': ObjectId(session['id'])
#             },
#             {
#                 'password': 0
#             }
#         )

#         return render_template('profile.html', member_data=member_data)
#     else:
#         return redirect('login')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('login')

@app.route('/admin_orderNo', methods=['GET', 'POST'])
def admin_orderNo():
    if 'display_name' in session:
        match = {}
        page_data = {}
        orderNo_data = []
        if request.method == 'POST':
            date = request.form['date']
            orderNo = request.form['orderNo']
            bankAccount = request.form['bankAccount']
            match = {
                "$or": [
                    {
                        "date": date
                    },
                    {
                        "order_no": orderNo
                    },
                    {
                        "used_oid": {
                            "$in": [bankAccount]
                        }
                    }
                ]          
            }

        orderNo_find = dbs.order_no.find(match)
        for doc in orderNo_find:
            doc['_id'] = str(doc['_id'])
            if doc['_id'] == '645253320dada5e817279de9':
                print(doc)
            if 'is_used' not in doc:
                doc['is_used'] = 'False'
            else:
                doc['is_used'] = 'True'
            orderNo_data.append(doc)
        return render_template('admin_orderNo.html', orderNo_data=orderNo_data, page_data=page_data)
    else:
        return redirect('admin_login')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        account = request.form['account']
        password = request.form['password']
        name = request.form['name']
        resetPassword = request.form['resetPassword']
        bankBranch = request.form['bankBranch']
        bankName = request.form['bankName']
        bankCard = request.form['bankCard']
        invitedCode = request.form['invitedCode']

        account_repeat = dbs.member.find_one({'account': account})
        if account_repeat != None:
            return redirect('register')

        print(account, password,   name, resetPassword,
              bankBranch, bankName, bankCard ,invitedCode)

        file_arr = []
        img_data = []
        imgUrl = ''
        file_arr.append(request.files['bankImage'])

        for f in file_arr:
            print('step2')
            if f and allowed_file(f.filename):
                file_path = basedir + '\public\image' + f'\{account}'
                print(file_path)
                if not os.path.isdir(file_path):
                    os.mkdir(file_path)
                f.save(os.path.join(file_path, f.filename))
                imgUrl = f'/image/{account}/{f.filename}'
                img_data.append(imgUrl)
            else:
                print('step3')
                return redirect('register')

        salt = '645464'
        password_str = password + salt
        user_password = hashlib.sha1(password_str.encode('utf-8'))

        dbs.bittop_member.insert_one({
            'account': account,
            'password': user_password.hexdigest(),
            'name':  name,
            'bankName': bankName,
            'bankBranch':bankBranch,
            'bankCard': bankCard,
            'USDT': 0,
            'img_data': img_data,
            'bonus_rate': 0,
            'status': False,
            'is_verify': 0,
            'salt': salt,
            'invitedCode':invitedCode
        })

        return '注册成功'
    else:
        return render_template('register.html')


@app.route('/api/<name>', methods=['GET', 'POST'])
def api(name):
  if name == 'fake_data' and request.method == 'GET':
    count = int(request.args.get('count'))
    fake_data = []
    number_list = random_number(count)
    for number in number_list:
      fake_find = dbs.fake_data.find_one({ "number": number }, { '_id': 0 })
      fake_data.append(fake_find)
    return jsonify(fake_data)
  elif name == 'factory_product' and request.method == 'POST':
    data = request.get_json()
    product_data = {
      "name": data['name'],
      "price": int(data['price']),
      "desc": "",
      "is_buy": False,
      "factory_bank": data['factory_bank'],
      "factory_name": data['factory_name']
    }
    dbs.product.insert_one(product_data)
    return jsonify({
      "message": "success"
    }), 200
  elif name == 'get_current_order':
    data = request.get_json()
    orderNo_data = []
    old_date = datetime.strptime(data['date'], '%Y-%m-%d')
    start_date = old_date + timedelta(days=1)
    start_date = start_date.strftime('%Y-%m-%d')
    end_date = old_date + timedelta(days=3)
    end_date = end_date.strftime('%Y-%m-%d')
    orderNo_find = dbs.order_no.find(
      {
        'date': {'$gte': start_date, '$lte': end_date}
      }
    )
    for doc in orderNo_find:
      repeat = False
      doc['_id'] = str(doc['_id'])
      for item in doc['used_oid']:
        if item == data['id']:
          repeat = True
      if repeat == False:
        orderNo_data.append(doc)
    return jsonify({
      'data': orderNo_data,
      'status': 'success'
    })
  else:
    return redirect(url_for('login'))

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False, port=5858)
