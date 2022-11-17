#!/usr/bin/env python
import datetime
import random
from collections import OrderedDict

import json
import inspect
import sys
from flask import Flask, request, jsonify, render_template, redirect, g
import sqlite3
import random

import plotly
import plotly.express as px
import plotly.graph_objs as go
import pandas as pd


debug_level = 4

app = Flask(__name__)
# important!!! the controler expects the json parameters in specific order
app.config['JSON_SORT_KEYS'] = False


def SetDebugLevel(level):
    global debug_level

    debug_level = level


def debug(msg, level=5):
    global debug_level

    if level >= debug_level:
        try:
            cf = inspect.stack()[1]
            cfile = cf.filename.split('/')[-1]
            cline = cf.lineno
            cfunction = cf.function
        except:
            cfile = 'NA'
            cline = 'NA'
            cfunction = 'NA'
        print('[%s] [%d] [%s:%s:%s] %s' % (datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), level, cfile, cfunction, cline, msg), file=sys.stderr, flush=True)


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect('database.sqlite3')
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def read_timers():
    '''Read the timers data from the tsv file
    '''
    pass


def get_state():
    con = get_db()
    cur = con.cursor()
    cur.execute('SELECT state FROM thermobit WHERE idx=1 LIMIT 1')
    res = cur.fetchone()
    if res is None:
        debug('Table empty, creating initial entry')
        cur.execute('INSERT INTO thermobit VALUES (1, ?)', [json.dumps({'pita':'pata','googu':23})])
        con.commit()
        data = {}
    else:
        data = json.loads(res[0])
        debug(data)
    debug('got cursor')
    # convert to datetimes
    cdata = data.copy()
    for ck,cv in data.items():
        if isinstance(cv, float):
            if cv<0:
                cdata[ck] = datetime.datetime.fromtimestamp(-cv)
    debug('read state %s' % cdata)
    return cdata


def write_state(state):
    con = get_db()
    cur = con.cursor()
    cstate = state.copy()
    # need to convert the datetimes so can serialize (we do it as negative floats since epoch)
    for ck,cv in state.items():
        if isinstance(cv, datetime.datetime):
            cstate[ck] = -cv.timestamp()
    debug('writing state %s' % cstate)
    cur.execute('UPDATE thermobit SET state=? WHERE idx=1', [json.dumps(cstate)])
    con.commit()
    debug('updated state')


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
    debug('test')
    write_state({'googa':'gogo','batata':True})
    state = get_state()
    debug(state)   
    return 'pita'


@app.route('/get_temp')
def get_temp():
    '''Get the current and set temperature'''
    debug('get_temp')
    state = get_state()
    res = jsonify({'current_temp': state.get('current_temp'), 'set_temp':state.get('set_temp')})
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
    debug('set_temp to %s' % set_temp)
    state = get_state()
    set_temp = int(request.args.get('set_temp', -1))
    current_temp = state.get('current_temp', -1)
    debug('set_temp: current:%d , set:%d' % (current_temp, set_temp))
    # check if need to turn on the heater
    if set_temp >= 0:
        debug('setting temp to %d' % set_temp)
        state['set_temp'] = set_temp
        state['set_temp_time'] = datetime.datetime.now()
        write_state(state)
        return 'temp_set:%d' % set_temp


@app.route('/main')
def main_page(set_temp=None):
    state = get_state()
    set_temp = int(request.args.get('set_temp', -1))
    current_temp = state.get('current_temp', -1)
    debug('main: current:%d , set:%d' % (current_temp, set_temp))

    # check if need to turn on the heater
    if set_temp >= 0:
        debug('setting temp to %d' % set_temp)
        state['set_temp'] = set_temp
        state['set_temp_time'] = datetime.datetime.now()
        write_state(state)
        return redirect('/main')

    debug('preparing graph')
    temp_graph = create_temp_graph()
    debug('graph created')
    return render_template('main.html', plot=temp_graph, current_temp=current_temp, set_temp = state.get('set_temp',-1), current_set_temp = set_temp, set_temp_time = state.get('set_temp_time').strftime('%Y-%m-%d %H:%M'))


def calc_hash(heater, hash=181):
    '''Calculate the checksum for the upate message response to the controller
    It is a single hex byte string
    We used hash=12 for processing all numbers as int
    But turns out the SetTemp needs to be treated as str
    '''
    for ck, cv in heater.items():
        if ck == 'SetTemp':
            debug('%s' % type(cv))
            # cv = str(cv)
            cv = str(int(cv))
        if isinstance(cv, float):
            debug('BATATA %s %s' % (ck, cv))
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

@app.route('/programs/add/', methods=['POST','GET'])
def programs_add():
    data = request.get_json()
    debug('********programs/add/****************')
    debug(data)
    debug('********/programs/add/****************')

    heater = OrderedDict()
    heater['Id'] = 0
    heater['IsOn'] = False
    heater['CurrentTemp'] = 49
    heater['SetTemp'] = 10
    heater['Now'] = '7,20:00'
    heater['UserNumber'] = 25564181
    heater['ProgramNumber'] = 3
    heater['Mode'] = 'PRG'
    heater['Prg'] = '19:00,10'

    checkSum = "{:02x}".format(calc_hash(heater)).upper()

    res = {'heater': heater, 'checkSum': checkSum}
    # res = {'heater': heater}

    return 'Thermobit'

    return jsonify(res)


@app.route('/controller/create/', methods=['POST','GET'])
def controller_create():
    # data = request.get_json()
    debug('********/controller/create/****************')
    # debug(data)
    debug('******/controller/create/******************')
    return 'Thermobit'

    heater = OrderedDict()
    heater['Id'] = 0
    heater['IsOn'] = False
    heater['CurrentTemp'] = 49
    heater['SetTemp'] = 10
    heater['Now'] = '7,20:00'
    heater['UserNumber'] = 25564181
    heater['ProgramNumber'] = 3
    heater['Mode'] = 'PRG'
    heater['Prg'] = '19:00,10'

    checkSum = "{:02x}".format(calc_hash(heater)).upper()

    res = {'heater': heater, 'checkSum': checkSum}
    # res = {'heater': heater}
    
    return jsonify(res)


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

    debug('espcreate')
    data = request.get_json()
    debug(data)
    state = get_state()
    state['current_temp'] = data.get('CurTemp',0)
    with open('./temp_log.txt','a') as f:
        ctemp = data.get('CurTemp',0)
        now = datetime.datetime.now()
        date_str = now.strftime('%Y\t%m\t%d\t%H\t%M')
        f.write(date_str + '\t' + str(ctemp) + '\n')
    write_state(state)
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
    debug('updated')
    state = get_state()
    user_number = request.args.get('UserNumber', None)
    debug(user_number)

    # need to setup in the correct order
    heater = OrderedDict()
    heater['Id'] = random.randint(-1, 5)
    heater['IsOn'] = False
    heater['CurrentTemp'] = 49
    heater['SetTemp'] = 49

    state['start_hour'] = 19
    state['start_min'] = 10

    now = datetime.datetime.now()
    # check if we need to turn on the boiler based on the daily timers
    if state.get('new_day', False):
        debug('new day')
        start_hour = state.get('start_hour',None)
        start_min = state.get('start_min', None)
        if start_hour is not None and start_min is not None:
            daynum = now.strftime('%w')
            day = chr(ord(daynum)+1)
            if datetime.time(start_hour,start_min) < datetime.time(now.hour, now.minute):
                debug('turning heater on because timer has begun')
                state['set_temp'] = state.get('timer_temp', -1)
                state['set_temp_time'] = now
                state['new_day'] = False
                state['last_day'] = now.day
                write_state(state)
            else:
                debug('timer has not started yet')

    # check if a new day has begun - for the daily timers
    last_day = state.get('last_day',-1)
    current_day = now.day
    if last_day != current_day:
        state['last_day'] = current_day
        state['new_day'] = True
        write_state(state)

    # check if we need to keep the heater on:
    current_temp = state.get('current_temp', -1)
    set_temp = state.get('set_temp', -1)
    set_temp_time = state.get('set_temp_time', None)
    debug('updated(): current_temp: %d' % current_temp)

    if current_temp < set_temp:
        debug('temp still lower')
        # check if are not heating for over 1 hour
        if set_temp_time + datetime.timedelta(hours=1) >= datetime.datetime.now():
            debug('need to heat, heater temp set to %d '% set_temp)
            heater['SetTemp'] = set_temp
        else:
            # TODO: need to send an email notification
            debug('Heater for over 1 hour and still did not reach the set temperature')
            set_temp = 6
            state['set_temp'] = set_temp
            write_state(state)
            heater['SetTemp'] = set_temp
    else:
        # set_temp 6 means the heater should be off
        if set_temp != 6:
            # we reached the set temperature, so stop heating
            # maybe send a message that the temperature has been reached (alexa? email?)
            debug('Temperature %d reached (current temp is %d)' % (set_temp, current_temp))
            set_temp = 6
            state['set_temp'] = set_temp
            write_state(state)
        else:
            debug('heater off')
        heater['SetTemp'] = set_temp

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


    # heater['Id'] = 0
    # heater['IsOn'] = False
    # heater['CurrentTemp'] = 49
    # heater['SetTemp'] = 10
    # heater['Now'] = '7,20:00'
    # heater['UserNumber'] = 25564181
    # heater['ProgramNumber'] = 3
    # heater['Mode'] = 'PRG'
    # heater['Prg'] = '19:00,10'

    # checkSum = 'E4'

    # checkSum = hex(random.randint(0,255))[2:]
    # if len(checkSum) == 1:
    #     checkSum = '0'+checkSum
    # checkSum = checkSum.upper()

    checkSum = "{:02x}".format(calc_hash(heater)).upper()

    res = {'heater': heater, 'checkSum': checkSum}
    # res = {'heater': heater}
    debug(res)
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


def gunicorn(debug_level=6):
    '''The entry point for running the api server through gunicorn (http://gunicorn.org/)
    to run thermobyte using gunicorn, use:

    gunicorn 'server:gunicorn(debug_level=4)' -b 0.0.0.0:80 --workers 1 --name=thermobit


    Parameters
    ----------
    debug_level: int, optional
        The minimal level of debug messages to log (10 is max, ~5 is equivalent to warning)

    Returns
    -------
    Flask app
    '''
    SetDebugLevel(debug_level)
    app.debug = True
    debug('starting thermobit server using gunicorn, debug_level=%d' % debug_level, 6)
    return app


if __name__ == '__main__':
    SetDebugLevel(5)
    debug('starting server',6)
    app.run(host='0.0.0.0', port=80, use_reloader=False, threaded=True)
    debug('Finished')
