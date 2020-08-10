# -*- coding: utf-8 -*-
from flask import Flask, jsonify, redirect, url_for,render_template, request
import const
import time
import hashlib
import requests
import json
from mongoApi import ZhiBoMongoApi
from flask_cors import CORS
from flask_login import login_required, LoginManager, login_user
from  flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import User

app = Flask(__name__, static_folder="./dist/static", template_folder="./dist",)

CORS(app, supports_credentials=True)
limiter = Limiter(app, key_func=get_remote_address)
app.secret_key = 'qwert123456'
login_manager = LoginManager()
login_manager.session_protection = 'strong'
login_manager.init_app(app)
login_manager.login_view = 'index'
collection_name = ZhiBoMongoApi(const.DATABASE)


def mac_mini():
    return "mac_mini 添加 20200810"
def chongtu():
    return '测试冲突'

@app.route('/api/login',methods=["GET","POST"])
@limiter.exempt
def login():
    data = json.loads(request.get_data().decode('utf-8'))
    code = data['platCode']
    req_params = {
        'appid': const.appID,
        'secret': const.appSecret,
        'js_code': code,
        'grant_type': 'authorization_code'
    }
    response_data = requests.get(const.code2_session, params=req_params)
    res = response_data.json()
    openid = res["openid"]

    encrypts = hashlib.sha1(res["session_key"]).hexdigest()

    if collection_name.find_user({"openid": openid}):
        collection_name.update_user({"openid": openid}, {"$set": {"session_key": res.get('session_key')}})
    else:
        collection_name.insert_user(res)
    return json.dumps({"success": True, "msg": "login success", "userinfo": {"token_key": encrypts, "openid": openid}})


@app.route('/api/anchor_list', methods=["GET"])
@limiter.exempt
def get_anchor_list():
    openId = request.args.get('openId')
    current_time = time.strftime("%Y-%m-%d", time.localtime())
    # print current_time,type(current_time)
    query = {"touser": openId, 'date': current_time}
    follow_data = collection_name.find_follow_anchor(query)
    all_data = collection_name.find_anchor_list({"date": current_time})
    # print type(all_data)
    if follow_data:
        # 处理用户关注的数据
        for follow in follow_data:
            anchorId = follow["anchorId"]
            items = follow["items"]
            data = list(collection_name.find_anchor_list({"date": current_time,"anchorId": anchorId}))[0]
            index = all_data.index(data)
            all_data[index]['isFollow'] = True
            if items:
                all_data[index]["items"] = items
        return jsonify(all_data)
    else:
        return jsonify(all_data)


@app.route('/api/follow_anchor', methods=["POST"])
@limiter.limit("1/second")
def follow_anchor():
    data = json.loads(request.data)
    token_key = data.get("token_key")

    res = collection_name.find_user({"openid": data["touser"]})
    print "res",res
    if hashlib.sha1(res[0].get('session_key', '')).hexdigest() != token_key or len(res) == 0:
        return jsonify({'success': False, 'error': 'token error'})

    data["date"] = time.strftime("%Y-%m-%d", time.localtime())
    try:
        collection_name.insert_follow_anchor(data)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/cancel_anchor', methods=["POST"])
@limiter.limit("1/second")
def cancel_anchor():
    data = json.loads(request.data)
    data["date"] = time.strftime("%Y-%m-%d", time.localtime())
    token_key = data.get("token_key")
    res = collection_name.find_user({"openid": data["touser"]})
    if hashlib.sha1(res[0].get('session_key', '')).hexdigest() != token_key or len(res) == 0:
        return jsonify({'success': False, 'error': 'token error'})
    try:
        collection_name.remove_follow_anchor(data)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': e})


@app.route('/api/update_follow', methods=["POST"])
@limiter.limit("1/second")
def update_follow():
    data = json.loads(request.data)
    token_key = data.get("token_key")
    res = collection_name.find_user({"openid": data["touser"]})
    if hashlib.sha1(res[0].get('session_key', '')).hexdigest() != token_key or len(res) == 0:
        return jsonify({'success': False, 'error': 'token error'})
    try:
        query = {
            "anchorId": data["anchorId"],
            "touser": data["touser"],
            "date": time.strftime("%Y-%m-%d", time.localtime())
        }
        print query
        print data["items"]
        collection_name.update_follow_anchor(query, {"$set": {"items": data["items"]}})
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/feedback', methods=["POST"])
def feedback():
    try:
        data = json.loads(request.data)
        collection_name.insert_feedback(data)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# @app.route('/api/checksignature',methods=['GET',"POST"])
# def check_signature():
#     if request.method == 'GET':
#         signature = request.args.get('signature')
#         echostr = request.args.get('echostr')
#         timestamp = request.args.get('timestamp')
#         nonce = request.args.get('nonce')
#         token = 'asdfsdf'
#         tmp_list = [token,timestamp,nonce]
#         tmp_list.sort()
#         tmpStr = tmp_list[0] + tmp_list[1] + tmp_list[2]
#         tmpStr = hashlib.sha1(tmpStr).hexdigest()
#         if tmpStr == signature:
#             return echostr
#         else:
#             return ""
#     else:
#         print "推送"


# ------------------------------------------- 分割 --------------------


@app.route('/api/feedback_list')
def feedback_list():
    anchor_list = collection_name.feedback_distinct('anchor')
    data = []
    for anchor in anchor_list:
        data.append({
            'anchor': anchor,
            'count': len(collection_name.find_feedback({"anchor": anchor}))
        })
    return jsonify({"success": True, 'feedback': data})


# 获取登录用户的方法
@login_manager.user_loader
def load_user(user_id):
    return User.User.get(int(user_id))


@app.route('/')
def index():
    return render_template("index.html")

@app.route('/api/admin_login', methods=["POST"])
def admin_login():
    userInfo = json.loads(request.data)
    print userInfo
    password = userInfo["password"]
    # 创建用户实例
    if userInfo['id'] == 1:
        p_ha = "pbkdf2:sha1:1000$M14XrOS6$aded4392ded547bcd9d266f099d39de5d81ad40c"
    if userInfo['id'] == 2:
        p_ha = "pbkdf2:sha1:1000$GqUaitQC$7ade263cdcd1e6ca1153b102bde442f4214eebbf"
    if userInfo['id'] == 3:
        p_ha = "pbkdf2:sha1:1000$BSUPw9oN$b43bc3a9ad65db1a00ad022b14e128d9a7090d1d"
    if userInfo['id'] == 4:
        p_ha = "pbkdf2:sha1:1000$y1ZB8GlG$79f33710b233b5a697a49b78cc0d2c79a63438ca"
    user = User.User(
        {
            "id": userInfo['id'],
            "name": userInfo['name'],
            "password": p_ha
        }
    )
    if user.verify_password(password):
        print '验证通过'
        login_user(user)
        return jsonify({"success": True})
    else:
        print '验证失败'
        return jsonify({"success": False})


@app.route('/api/send_message', methods=["POST"])
#@login_required
def send_message():
    # access 有效期2个小时
    res = requests.get(const.access_token_url).text
    access_token = json.loads(res)["access_token"]
    data = json.loads(request.data)
    anchorId = data["anchorId"]
    item = data["item"]
    items = data["items"]
    date = time.strftime("%Y-%m-%d", time.localtime())
    follow_data = collection_name.find_follow_anchor({"anchorId": anchorId, "date": date})
    anchor_data = list(collection_name.find_anchor_list({"anchorId": anchorId, "date": date}))[0]
    if follow_data:
        for follow in follow_data:
            items = follow["items"]
            openId = follow["touser"]
            params = {
                "touser": openId,
                "template_id": const.template_id,
                "data": {
                    "thing1": {"value": str((anchor_data["anchor"] + item).encode('utf-8'))  + '的直播即将开始' },
                    "date2": {"value": anchor_data["date"]},
                    "thing3": {"value": str(anchor_data["platform"].encode('utf-8')) + '直播间'},
                }
            }
            if item == "":
                try:
                    con = requests.post(const.send_message_url + access_token, data=json.dumps(params))
                    print openId, 'notice', con.text
                except Exception as e:
                    print 'error', e
            else:
                for itemDict in items:
                    if itemDict["name"] == item and itemDict["checked"] == True:
                        try:
                            con = requests.post(const.send_message_url + access_token, data=json.dumps(params))
                            print openId, 'notice',con.text
                        except Exception as e:
                            print 'error',e
        return jsonify({"Success": True})
    else:
        print 'no user follow'
        return jsonify({'success': False, 'message': 'no user follow'})


@app.route('/api/add_anchor', methods=["POST"])
# @login_required
def insert_anchor():
    try:
        data = json.loads(request.data)
        logo = const.STATIC_LOCATION + data['logo']
        data["logo"] = logo
        collection_name.insert_anchor(data)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route('/api/delete_anchor', methods=["POST"])
# @login_required
def delete_anchor():
    try:
        data = json.loads(request.data)
        collection_name.remove_anchor({"anchorId":data["anchorId"]})
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route('/api/update_anchor', methods=["POST"])
# @login_required
def update_anchor():
    try:
        data = json.loads(request.data)
        query = {
            "anchorId": data["anchorId"]

        }
        logo = const.STATIC_LOCATION + data['logo']
        data['logo'] = logo
        collection_name.update_anchor(query, {"$set": data})
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route('/api/anchor_icon', methods=["GET"])
# @login_required
def anchor_icon():
    import os
    icon_list = []
    icon_data = []
    for files in os.walk('./dist/static/icon'):
    # for files in os.walk('./icon'):
        icon_list = files[2]
    for icon in icon_list:
        icon_data.append({
            'value': icon,
            'label': icon
        })
    print "icon_list",icon_list
    return jsonify({"success": True, 'icon_list': icon_data})


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)


