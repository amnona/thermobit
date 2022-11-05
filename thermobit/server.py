#!/usr/bin/env python
import datetime
import random
from collections import OrderedDict

import json
from flask import Flask, request, jsonify, render_template, redirect

import plotly
import plotly.express as px
import plotly.graph_objs as go
import pandas as pd


app = Flask(__name__)
# important!!! the controler expects the json parameters in specific order
app.config['JSON_SORT_KEYS'] = False

class AppState:
    def __init__(self):
        self.current_temp = 0
        self.set_temp = 6
        self.set_temp_time = datetime.datetime.now()

app_state = AppState()


def debug(msg):
    print('%s: %s' % (datetime.datetime.now().strftime("%m/%d/%Y, %H:%M:%S"), msg))

def create_temp_graph():
    dat = pd.read_csv('./temp_log.txt',sep='\t')
    dat['y'] = dat['temp']
    dat['x'] = dat['date']*24*60 + dat['hour']*60 + dat['minute']
    fig = px.line(dat, x='x',y='y',title='temp')
    plot_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    return plot_json
    # data = [go.Bar(x=dat['x'],y=dat['y'])]
    # graphJSON = json.dumps(data, cls=plotly.utils.PlotlyJSONEncoder)
    # return graphJSON

@app.route('/test')
def test():
    print('test')
    return 'pita'


@app.route('/get_temp')
def get_temp():
    '''Get the current and set temperature'''
    global app_state
    res = jsonify({'current_temp': app_state.current_temp, 'set_temp':app_state.set_temp})
    debug('get_temp returned %s' % res)
    return res

@app.route('/set_temp')
def set_temp(set_temp=None):
    '''Update the set temperature. If we want to turn off, supply set_temp as 6
    
    Parameters:
    ----------
    set_temp: int
        the new temperature to set (6 to turn off)
    '''
    global app_state
    set_temp = int(request.args.get('set_temp', -1))
    current_temp = app_state.current_temp
    debug('set_temp: current:%d , set:%d' % (current_temp, set_temp))
    # check if need to turn on the heater
    if set_temp >= 0:
        debug('setting temp to %d' % set_temp)
        app_state.set_temp = set_temp
        app_state.set_temp_time = datetime.datetime.now()
        return 'temp_set:%d' % set_temp


@app.route('/main')
def main_page(set_temp=None):
    global app_state
    set_temp = int(request.args.get('set_temp', -1))
    current_temp = app_state.current_temp
    debug('main: current:%d , set:%d' % (current_temp, set_temp))

    # check if need to turn on the heater
    if set_temp >= 0:
        debug('setting temp to %d' % set_temp)
        app_state.set_temp = set_temp
        app_state.set_temp_time = datetime.datetime.now()
        return redirect('/main')

    temp_graph = create_temp_graph()
    return render_template('main.html', plot=temp_graph, current_temp=current_temp, set_temp = app_state.set_temp, current_set_temp = set_temp, set_temp_time = app_state.set_temp_time.strftime('%Y-%m-%d %H:%M'))


def calc_hash(heater, hash=181):
    '''Calculate the checksum for the upate message response to the controller
    It is a single hex byte string
    We used hash=12 for processing all numbers as int
    But turns out the SetTemp needs to be treated as str
    '''
    for ck, cv in heater.items():
        if ck == 'SetTemp':
            cv = str(cv)
        if isinstance(cv, int):
            for x in cv.to_bytes(4,'big'):
                hash = hash+x
                # hash = hash ^ x
        else:
            for x in cv:
                hash = hash+ord(x)
                # hash = hash ^ ord(x)
    hash = hash%256
    return hash


@app.route('/home/espcreate/', methods=['POST','GET'])
def espcreate():
    '''this is an update message from the controller. includes the current state of the controller in json parameters:
    'IsOn': 0, ???
    'CurTemp': 28, the current water temperature
    'SetTemp': 15, the set water temperature (manual?)
    'PrgNum': 0, ???
    'UsrNum': 25564181, the controller id
    'Mode': 'MAN' manual or 'PRG' program

    Expected return value:
        empty - just acknowledge we got the message
    '''
    global current_temp
    global app_state

    print('espcreate')
    data = request.get_json()
    print(data)
    app_state.current_temp = data.get('CurTemp',0)
    with open('./temp_log.txt','a') as f:
        ctemp = data.get('CurTemp',0)
        now = datetime.datetime.now()
        date_str = now.strftime('%Y\t%m\t%d\t%H\t%M')
        f.write(date_str + '\t' + str(ctemp) + '\n')
    return ''

@app.route('/home/updated')
def updated():
    '''Set the controller parameters based on values from the server
    The controller originates this message every 15sec and asks what to set
    Parameters:
    UserNumber: the unit number (as supplied in the UsrNum parameter in espcreate)
    
    Returns:
    Object
        Member: heater
            Object
                Member: Id
                    [Path with value: /heater/Id:0]
                    [Member with value: Id:0]
                    Number value: 0
                    Key: Id
                    [Path: /heater/Id]
                Member: IsOn
                    [Path with value: /heater/IsOn:false]
                    [Member with value: IsOn:false]
                    False value
                    Key: IsOn
                    [Path: /heater/IsOn]
                Member: CurrentTemp
                    [Path with value: /heater/CurrentTemp:49]
                    [Member with value: CurrentTemp:49]
                    Number value: 49
                    Key: CurrentTemp
                    [Path: /heater/CurrentTemp]
                Member: SetTemp
                    [Path with value: /heater/SetTemp:10]
                    [Member with value: SetTemp:10]
                    Number value: 10
                    Key: SetTemp
                    [Path: /heater/SetTemp]
                Member: Now
                    [Path with value: /heater/Now:7,19:45]
                    [Member with value: Now:7,19:45]
                    String value: 7,19:45
                    Key: Now
                    [Path: /heater/Now]
                Member: UserNumber
                    [Path with value: /heater/UserNumber:25564181]
                    [Member with value: UserNumber:25564181]
                    Number value: 25564181
                    Key: UserNumber
                    [Path: /heater/UserNumber]
                Member: ProgramNumber
                    [Path with value: /heater/ProgramNumber:3]
                    [Member with value: ProgramNumber:3]
                    Number value: 3
                    Key: ProgramNumber
                    [Path: /heater/ProgramNumber]
                Member: Mode
                    [Path with value: /heater/Mode:PRG]
                    [Member with value: Mode:PRG]
                    String value: PRG
                    Key: Mode
                    [Path: /heater/Mode]
                Member: Prg
                    [Path with value: /heater/Prg:19:00,10]
                    [Member with value: Prg:19:00,10]
                    String value: 19:00,10
                    Key: Prg
                    [Path: /heater/Prg]
            Key: heater
            [Path: /heater]
        Member: checkSum
            [Path with value: /checkSum:E4]
            [Member with value: checkSum:E4]
            String value: E4
            Key: checkSum
            [Path: /checkSum]

    '''
    global app_state
    user_number = request.args.get('UserNumber', None)
    heater = {}
    heater = OrderedDict()
    heater['Id'] = 0
    heater['IsOn'] = False
    heater['CurrentTemp'] = 49

    # check if we need to keep the heater on:
    debug('updated(): current_temp: %d' % app_state.current_temp)
    if app_state.current_temp < app_state.set_temp:
        debug('temp still lower')
        # check if are not heating for over 1 hour
        if app_state.set_temp_time < datetime.datetime.now()+datetime.timedelta(hours=1):
            debug('need to heat, heater temp set to %d '% app_state.set_temp)
            heater['SetTemp'] = app_state.set_temp
        else:
            # TODO: need to send an email notification
            debug('Heater for over 1 hour and still did not reach the set temperature')
            app_state.set_temp = 7
            heater['SetTemp'] = app_state.set_temp
    else:
        # we reached the set temperature, so stop heating
        # maybe send a message that the temperature has been reached (alexa? email?)
        debug('Temperature %d reached (current temp is %d)' % (app_state.set_temp, app_state.current_temp))
        app_state.set_temp = 6
        heater['SetTemp'] = app_state.set_temp

    now = datetime.datetime.now()
    # we add one day since days for the controller are 1 indexed (sun=1, sat=7)?
    daynum = now.strftime('%w')
    day = chr(ord(daynum)+1)
    heater['Now'] = day + now.strftime(',%H:%M')
    # heater['Now'] = '7,21:45'
    heater['UserNumber'] = int(user_number)
    heater['ProgramNumber'] = 3
    heater['Mode'] = 'MAN'
    heater['Prg'] = '19:00,45'



    # checkSum = 'E4'
    # checkSum = hex(random.randint(0,255))[2:]
    # if len(checkSum) == 1:
    #     checkSum = '0'+checkSum
    # checkSum = checkSum.upper()
    checkSum = "{:02x}".format(calc_hash(heater)).upper()

    res = {'heater': heater, 'checkSum': checkSum}
    # res = {'heater': heater}
    # debug(res)
    return jsonify(res)

@app.route('/api/token', methods=['post'])
def api_token():
    print('api_token')
    return

@app.route('/api/accounts/get', methods=['get'])
def api_accounts_get():
    print('api_accounts_get')
    return

@app.route('/api/remotes/get/state', methods=['get'])
def api_remotes_get_state():
    print('api_remotes_get_state')
    return 'batata'

@app.route('/api/remotes/set/manual', methods=['post'])
def api_remotes_set_manual():
    print('api_remotes_set_manual')
    return

@app.route('/api/remotes/set/scheduled', methods=['post'])
def api_remotes_set_scheduled():
    print('api_remotes_set_scheduled')
    return

@app.route('/version/IsAlive', methods=['get'])
def version_is_alive():
    print('version_is_alive')
    return 'Thermobit'

@app.route("/")
def hello_world():
    print('hello_world')
    return "<p>Hello, World!</p>"

if __name__ == '__main__':
    print('starting')
    app.run(host='0.0.0.0', port=80)
    print('done')
