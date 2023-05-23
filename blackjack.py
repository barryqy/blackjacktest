import os, time, sys
import jsonpickle,json
from flask import Flask, render_template, request
from pathlib import Path    # for dumping and reloading state of the game
from classes import GameBlackJack, PlayerBlackJack, PlayerBlackJackHouse
from flask_socketio import SocketIO, join_room

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins = '*')
#gamedata = json.dumps({})

def prwarn(prt):
    print(f"\033[94m{prt}\033[00m")

prwarn("#########!!!CLICK_LINK_BELOW_TO_PLAY_BLACKJACK!!!#########")
prwarn(os.environ["DEVENV_APP_8080_URL"])
prwarn("#"*58)

#@app.route("/api", methods=['GET', 'POST'])
#def index():
#    if request.method == 'GET':
#        return json.dumps( GameBlackJack.getactivemultiplayerinfo() )
#    elif request.method == 'POST':
#        data = request.json
#        # Process the data and return a response
#        response = {'message': 'Received POST request', 'data': data}
#        return json.dumps(response)
    
@app.route("/api/gamestatejson", methods=['GET', 'POST'])
def gamestate():
    if request.method == 'GET':
        return GameBlackJack.getstatejson()
    elif request.method == 'POST':
        return GameBlackJack.poststatejson(request.json)
    
@app.route("/api/config", methods=['GET','POST'])
def config():
    if request.method == 'GET':
        return readconfig()
    elif request.method == 'POST':
        gamedata = request.json
        print("gamestart")
        print(json.dumps(gamedata))
        result = writeconfig(gamedata)
        # Process the data and return a response
        response = {'message': result}
        return json.dumps(response)
def writeconfig(data):
    try:
        if(not os.path.isdir(GameBlackJack.CONFIG_DIR)):
            os.mkdir(GameBlackJack.CONFIG_DIR)
        filepath = Path('{}/{}'.format(GameBlackJack.CONFIG_DIR, 'config'))
        with open(filepath, 'w') as filehandle:                        
            json.dump(jsonpickle.encode(data), filehandle)
        return "Successful"
    except Exception as e:
        return "Failed"
def readconfig():
    filepath = Path('{}/{}'.format(GameBlackJack.CONFIG_DIR, 'config'))
    with open(filepath, 'r') as filehandle:
        return jsonpickle.decode(json.load(filehandle))

@app.route("/api/leader", methods=['Post'])
def leader_refresh():
    socketio.emit('leader_refresh', request.json)
    response = {'message': "Success"}
    return json.dumps(response)

@app.route("/", methods=['GET'])
def frontpage():    
    return render_template('cards.html')

@app.route("/leader", methods=['GET'])
def leader():
    return render_template('leader.html')
    
def messageReceived(methods=['GET', 'POST']):
    debugout('received.')

@socketio.on('connected')
def on_connected(json, methods=['GET', 'POST']):
    debugout('Client connected:{0} {1}'.format(str(json), request.sid))    
    socketio.emit('my response', json, callback=messageReceived, room="xdr")

@socketio.on('list_multiplayer_games')
def list_games( methods=['GET', 'POST']):
    #debugout('{0}: list multiplayer games'.format(data['player_name'], data['bet_amount']))    
    json_response = json.dumps( GameBlackJack.getactivemultiplayergames() )
    socketio.emit('display_multiplayer_games', json_response, callback=messageReceived)

@socketio.on('join_game')
def joingame(methods=['GET', 'POST']):
    """player joins the game (only for multiplayer game)    
    
    PARAMETERS:
    gameid -- id of the multiplayer game
    bet_amount -- amount of money player bets on this game
    player_name -- name of the first player
    """
    gamedata = readconfig()
    if gamedata == json. dumps({}):
        print("game not ready")
    else:
        gameid = gamedata['gameid']
        player_name = gamedata['player_name']
        amount = int(gamedata['bet_amount'])
        debugout('{0} {1} joined. bet = {2} USD'.format(gameid, player_name, amount))

        firstplayer = PlayerBlackJack(gamedata['player_name'], gamedata['balance'])    
        firstplayer.bet(int(gamedata['bet_amount']))  
        game = GameBlackJack(PlayerBlackJackHouse(), gameid = request.sid) #<----this request.sid is weird, find out why!!!!!!!!
        game.gameid=gameid
        #game = GameBlackJack(PlayerBlackJackHouse(), gameid)
        game.addplayer(firstplayer)
        
        # TODO: Currently all users create rooms which is wrong, appoint first user to create room, others automatically join room!!!!!!!!!
        game.multiplayer = True        
        join_room(game.gameid)
        debugout("{}: creates room {}".format(firstplayer.name, game.gameid))
        game.dumpstate() # save the game state
        #socketio.emit('wait_others', None, callback=messageReceived) # TODO: maybe unicast would be better here ...
        
        #Wait for XDR to dump state to game
        """
        while game.deck_id == "":
            for cursor in '\\|/-':
            time.sleep(0.1)
            # Use '\r' to move cursor back to line beginning
            # Or use '\b' to erase the last character
            sys.stdout.write('...Waiting for XDR\r{}'.format(cursor))
            # Force Python to write data into terminal.
            sys.stdout.flush()
        """
        gamestart(game)
      
def gamestart(game):
    """ Start game of BlackJack and give turn to the first player (or end immediately) """
    
    debugout('{1} - game start'.format(game.players[0].name, game.gameid))
     
    oktocontinue = game.startgame()    
    msg=''
    if(not oktocontinue):   # check if makes sense to continue playing
        msg = ','.join(game.settlebets())
    
    while(game.playerturn.has21() and game.playerturn.name != 'house'): # skip players who already have 21
        game.nextplayer()

    payload = getpayload(game, msg, None, oktocontinue)
    #debugout('{0} send response to room'.format(gameid, payload))
    game.dumpstate()
    #print(json.dumps(payload))
    socketio.emit('game_start', json.dumps(payload), callback=messageReceived, room=game.gameid)
    
@socketio.on('game_restart')
def gamerestart(data, methods=['GET', 'POST']):
    """Restart the game 
    
    PARAMETERS:
    gameid -- id of the game to restart
    """
    
    gameid = data['gameid']    
    debugout('{0} restart'.format(gameid))
    game = GameBlackJack.getstate(gameid)
    game.endgame()  # this cleans up the state for every player
    
    for player in game.players: # this is a hack, because GUI for betting round is not there yet)
        player.bet(int(data['bet']))
    gamestart(game)
    
@socketio.on('player_move')
def playermove(data, methods=['GET', 'POST']):
    """player makes a move    
    
    PARAMETERS:
    gameid -- id of the multiplayer game
    action -- hit | stand
    player_name -- name of the first player
    """
    
    gameid = data['gameid']
    action = data['action']
    name = data['player_name']
    debugout('{2} - {0} => {1}'.format(data['player_name'], action, gameid))
       
    game = GameBlackJack.getstate(gameid)
    if(game.playerturn.name != name):   # this shold not occur
        raise   #TODO: implement exception here
    
    playerfinished = game.playermove(game.playerturn, action)
    if(not playerfinished): # player is still on the move
        payload = getpayload(game, None, action, True)
        debugout(payload)        
        game.dumpstate()
        socketio.emit('player_move', json.dumps(payload), callback=messageReceived, room=game.gameid)
        return
    else: # player is finished. next player is selected   
        writeconfig({"gameid": gameid, "player_name": name, "bet_amount": "50", "balance": game.playerturn.money})     # Write config at every turn!!!!!!!! TODO: validate
        nextplayermove(game, action)

def nextplayermove(game, previous_action):  
    
    # determine next player for the move:
    game.nextplayer()
    while(game.playerturn.has21() and game.playerturn.name != 'house'):
        game.nextplayer()
    #debugout("Next player {}".format(game.playerturn))
    debugout('{1} - next player = {0}'.format(game.playerturn.name, game.gameid))    
    if(game.playerturn.name != 'house'):    # next player is on the move    
        payload = getpayload(game, None, previous_action, True)        
        debugout(payload)
        game.dumpstate()        
        socketio.emit('player_move', json.dumps(payload), callback=messageReceived, room=game.gameid)
    else:   # house is on the move and then game ends                
        game.housemove()        
        msg = game.settlebets()                  
        debugout(','.join(msg))
        payload = getpayload(game, ', '.join(msg), previous_action, False)
        game.endgame()
        game.dumpstate()
        debugout(payload)        
        json_response = json.dumps(payload)        
        socketio.emit('player_move', json_response, callback=messageReceived, room=game.gameid)

@socketio.on('disconnect')
def cleanup():
    debugout('{} disconnected'.format(request.sid))
    fs = Path('{}/{}'.format(GameBlackJack.SESSIONS_DIR, request.sid))    
    if(os.path.isfile(fs)):
        pass    #TODO cleanup session files

def getpayload(game, msg, action, uistate):
    player1_data = game.players[0].toDict()
    if(len(game.players) > 1):
        player2_data =  game.players[1].toDict()
    else:
        player2_data =  None
    
    turn = None    
    if(game.playerturn):
        turn = game.playerturn.name    
    return {'player': player1_data, 
            'player2': player2_data, 
            'house': game.house.toDict(),
            'action':action, 
            'gameid':game.gameid, 
            'player_turn': turn, 
            'game_state': uistate, 
            'msg': msg }

def debugout(msg):
    print(msg)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0',port=80, debug=True)