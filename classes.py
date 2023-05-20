import os                   # for dumping and reloading state of the game
import jsonpickle, json     # for dumping and reloading state of the game
import uuid                 # for dumping and reloading state of the game
from pathlib import Path    # for dumping and reloading state of the game
import random               # shuffling card decks TODO Remove after XDR integration
from glob import glob
class GameBlackJack:     
    SESSIONS_DIR = 'sessions'   # used to store game state on client container
    CONFIG_DIR = 'config'
    NATURAL = 21                # target of the game is 21
    MOVE_HIT = 'hit'
    MOVE_STAND = 'stand'
    
    def __init__(self, house, num_decks = 1, gameid = None):
        self.multiplayer = False
        self.num_decks = num_decks
        self.house = house
        self.house.prepareforgame()       
        self.decks = Decks(num_decks)
        self.players = []
        self.bets = 0
        self.playerturn = None
        self.gameid = gameid
        self.deck_id = ""
        
    def addplayer(self, player):
        """Adds a new player to the game.
        
        Player must have a unique name and had to have bet money on this game
        """
        if(player.money < 0):
            raise
        if(player.bet_amount <= 0):
            raise        
        if(player in self.players):
            raise
                
        player.prepareforgame() # reset player state in case he had played a round before             
        self.players.append(player)

    def isgameover(self):
        """Checks if either house >= 21 or all the players have >= 21"""
        
        if(self.house.has21() or self.house.isbust()):
            return True
        
        allplayersbust = True
        allplayers21 = True
        for p in self.players:
            if(not p.has21()):                
                allplayers21 = False
            if(not p.isbust()):
                allplayersbust = False
                
        return allplayersbust or allplayers21
    
    def playermove(self, player, move):
        """Player can either take a new card (hit) or wait (stand).
        
        Arguments:
        move -- GameBlackJack.MOVE_HIT | GameBlackJack.MOVE_STAND
        
        Functions returns True if player can do another move or False if player is bust or has hit Blackjack.
        """
        
        if(move == GameBlackJack.MOVE_HIT):
            player.getcard(self.decks.popcard())            
            return player.isbust() or player.has21()
        else:
            return True    
    
    def nextplayer(self):
        """ Called after one of the players has done the move to get the next player in order. The last player is always house. """
                
        if(isinstance(self.playerturn, PlayerBlackJackHouse)):  # this should never happen
            raise   #todo
        
        next_player = self.players.index(self.playerturn) + 1
        if(next_player < len(self.players)):
            self.playerturn = self.players[next_player] 
        else:
            self.playerturn = self.house    #after the last player has played it's house turn        
        return self.playerturn
    
    def housemove(self):
        """ House must stand if the total is 17 or more and take a card if the total is 16 or under """
        
        while(self.house.cardsvalue() < 17):                
                self.house.getcard(self.decks.popcard())                 
        self.playerturn = None  #house is the last player
            
    def settlebets(self):
        """Called after the game has finished to determine winners and losers and pay out money. 
        
        If house has 21, then player lose or tie if they also have 21.
        If house is bust player can win if they are not but lose if they are also bust.
        If house < 21, then players win if they are closer to 21, lose if they are over or tie
        """
        
        dbgmsg = [] #for UI and debugging purposes
        for p in self.players:
            if(self.house.has21()):
                if(p.has21()):      #player also has 21 it's a tie                    
                    dbgmsg.append(self.tie(p))  # player and house have a GameBlackJack.NATURAL
                else:
                    dbgmsg.append(self.housewins(p)) # player has lost
            elif(self.house.isbust()): #house > 21                
                if(not p.isbust()):
                    dbgmsg.append(self.playerwins(p)) #house is bust and player is not
                else:
                    dbgmsg.append(self.housewins(p)) #both house and player are bust so the houst wins 
            else: # house < 21
                if(p.has21()): #TODO: unnecessary               
                    dbgmsg.append(self.playerwins(p)) #player wins
                elif(p.isbust()):                    
                    dbgmsg.append(self.housewins(p))
                else: # nobody has 21, check who is closest
                    distancehouse = self.house.cardsdiff()             
                    distanceplayer = p.cardsdiff()
                    if(distancehouse < distanceplayer):
                        dbgmsg.append(self.housewins(p)) #house is closer to 21 than player
                    elif(distancehouse == distanceplayer):
                        dbgmsg.append(self.tie(p)) #player and house have the same points
                    else:
                        dbgmsg.append(self.playerwins(p)) #player is closer to 21 than house
        return dbgmsg
    
    def tie(self, player):
        """ Return the bet amount to player """
        
        player.tie()
        return "It's a tie between house and {}".format(player.name)

    def housewins(self, player):
        """ House takes player's bet """
                
        lost = player.loose()                    
        self.house.win(lost)
        return "{} lost".format(player.name)
        
    def playerwins(self, player):
        """ Player gets bet amount """
        
        amount = player.win()   #TODO: factor is more than 1.0 if blackjack                    
        self.house.loose(amount)
        return "{} won".format(player.name)
          
    def startgame(self):
        """ Give cards to each of the players and set the turn to the first player. """
        
        # first card is dealt face up
        for p in self.players:            
            p.getcard(self.decks.popcard())
                        
        # first card is dealt to the house face up
        self.house.getcard(self.decks.popcard())
        
        # second card is dealt face up
        for p in self.players:            
            p.getcard(self.decks.popcard())
        
        # second card is dealt to the house face down
        self.house.getcard(self.decks.popcard(facedown = True))
        
        self.playerturn = self.players[0]
        
        return not self.isgameover() # check if it makes sense to continue playing
    
    def endgame(self):
        """ Prepare for next round by resetting hands and bets for each of the players. Reshuffle cards."""
        
        self.house.prepareforgame()
        for p in self.players:
            p.prepareforgame()
        self.decks = Decks(self.num_decks) #TODO: is it ok to reshuffle after every round?
        self.playerturn = None
    
    def ismultiplayergame(self):
        return self.multiplayer
    
    def getplayerbyname(self, pname):
        for p in self.players:
            if(p.name.lower() == pname.lower()):
                return p
        raise   # TODO
        
    def dumpstate(self):
        if(not os.path.isdir(GameBlackJack.SESSIONS_DIR)):
            os.mkdir(GameBlackJack.SESSIONS_DIR)
        if(not self.gameid):
            self.gameid = str(uuid.uuid4())
        filepath = Path('{}/{}'.format(GameBlackJack.SESSIONS_DIR, self.gameid))
        
        #print(jsonpickle.encode(self, unpicklable=False))

        with open(filepath, 'w') as filehandle:                        
            json.dump(jsonpickle.encode(self), filehandle)
        return self.gameid
    
    @classmethod
    def getstate(cls, gameid):
        filepath = Path('{}/{}'.format(GameBlackJack.SESSIONS_DIR, gameid))
        with open(filepath, 'r') as filehandle:
            return jsonpickle.decode(json.load(filehandle))
    
    @classmethod
    def getactivemultiplayergames(cls):
        """ Helper method for UI - returns all active multiplayer game ids by looking at existing game files """
        #sess_files = glob.glob("{}".format(GameBlackJack.SESSIONS_DIR)).sort(key=os.path.getmtime, reverse=True) # get game files and sort descending by date
        sess_files = os.listdir("{}".format(GameBlackJack.SESSIONS_DIR))
        #print('{1}: {0}'.format(sess_files,"{}".format(GameBlackJack.SESSIONS_DIR)))        
        first_players = []
        game_ids = []
        for file in sess_files:
            #gid = file.split('\\')[1] #TODO check if backslash exists
            gid = file
            #print(gid)          
            game = GameBlackJack.getstate(gid)            
            if(game.multiplayer):
                first_players.append(game.players[0].name)
                game_ids.append(gid)
        gdict = {'games' : game_ids, 'names' : first_players }        
        return gdict
    
    @classmethod
    def getactivemultiplayerinfo(cls):
        """ Helper method for UI - returns all active multiplayer game ids by looking at existing game files """
        #sess_files = glob.glob("{}".format(GameBlackJack.SESSIONS_DIR)).sort(key=os.path.getmtime, reverse=True) # get game files and sort descending by date
        sess_files = os.listdir("{}".format(GameBlackJack.SESSIONS_DIR))
        #print('{1}: {0}'.format(sess_files,"{}".format(GameBlackJack.SESSIONS_DIR)))        
        first_players = []
        player_balance = []
        game_ids = []
        for file in sess_files:
            #gid = file.split('\\')[1] #TODO check if backslash exists
            gid = file
            print(gid)            
            game = GameBlackJack.getstate(gid)            
            if(game.multiplayer):
                first_players.append(game.players[0].name)
                player_balance.append(game.players[0].money)
                game_ids.append(gid)
        gdict = {'games' : game_ids, 'names' : first_players, 'player_balance' : player_balance } 
        print(str(gdict))       
        return gdict
    
    @classmethod
    def getstatejson(cls):
        file_list = glob(os.path.join(GameBlackJack.SESSIONS_DIR, "*"))
        sorted_files = sorted(file_list, key=os.path.getmtime, reverse=True)
        #filepath = Path('{}/{}'.format(GameBlackJack.SESSIONS_DIR, gameid))
        with open(sorted_files[0], 'r') as filehandle:
            return jsonpickle.encode(jsonpickle.decode(json.load(filehandle)), unpicklable=False)
        
    @classmethod
    def poststatejson(cls, gamedata):
        file_list = glob(os.path.join(GameBlackJack.SESSIONS_DIR, "*"))
        sorted_files = sorted(file_list, key=os.path.getmtime, reverse=True)
        #filepath = Path('{}/{}'.format(GameBlackJack.SESSIONS_DIR, gameid))
        with open(sorted_files[0], 'w') as filehandle:
            json.dump(jsonpickle.encode(gamedata), filehandle)
            return True
        
    def __repr__(self):            
        return "\n{1} {2}".format(len(self.decks.decks)/48, self.house, self.players)

class Card:
    """Card base class
    
    The card is represented by a tuple of (rank, suit)     
    """
    
    def __init__(self, r, s):  
        """Arguments:
        
        r -- rank
        s -- suit
        """         
        
        self._card = (r,s)
        self.facedown = False    
    
    def __repr__(self):            
        return "{}".format(self._card)
    
    def tonum(self):
        """Returns numeric representation this card in a deck (used for web interface)"""
        
        rank = self.RANK.index(self._card[0])
        suit = self.SUIT.index(self._card[1])        
        print('{0} => {1} ({2}, {3})'.format(self._card, (rank * suit), rank, suit))
        return (rank + suit * 13) + 1


class CardBlackJack(Card):
    """Card for Blackjack
    
    Values of Blackjack hand:
    hand 2 - 10 = face value
    hand J,Q,K = 10
    Ace = 1
    """
    
    RANK = [i for i in range(2, 11)] + ['JACK', 'QUEEN', 'KING', 'ACE']
    SUIT = ['SPADE', 'HEART ', 'CLUB', 'DIAMOND']
    
    def getval(self):
        """ Returns card value consistent with rules of blackjack. """
        
        if(self._card[0] not in ['JACK', 'QUEEN', 'KING', 'ACE']):
            return int(self._card[0])
        elif(self._card[0] == 'ACE'):
            return 1
        else:
            return 10
    
    def __repr__(self):
        #rname = '♠'
        #if(self._card[1] == 'HEART'):
        #    rname='♡'
        #elif(self._card[1] == 'DIAMOND'):
        #    rname='♢'
        #elif(self._card[1] == 'CLUB'):
        #    rname='♣'        
            
        return "{0}-{1}".format(self._card[1], self._card[0])


class Decks:    
    """ A stack of N decks hand """
    
    def __init__(self, num_decks = 1):
        """    
        Create a stack of num_decks of decks of hand. 
        Cards are shuffled automatically.        
        
        Arguments:
        num_decks -- number of decks    
        """
    
        self.decks = []
        ###### TODO Will need to remove the following as we're doing this through XDR
        for _ in range(0, num_decks):            
            self.decks += [CardBlackJack(r,s) for r in CardBlackJack.RANK for s in CardBlackJack.SUIT]
        random.shuffle(self.decks)
        
    def popcard(self, facedown = False):
        ###### TODO Replace the logic with XDR API
        card = self.decks.pop()
        card.facedown = facedown
        return card
    
    def __repr__(self):            
        return "{}".format([c.getval() for c in self.decks if not c.facedown])

class Player:    
    """Player in a betting card game.
    
    Player starts with some money and his name must be unique. PLayer's name cannot be house

    Methods
    -------
    win(factor = 1.0), 
    loose(), 
    tie()
        called after a game round is over. Player's money is increased or decreased based on game result.        
    bet(amount)
        called before a round starts to bet some money.
    prepareforgame()
        called after the round is over to reset the hand and bet amount
    getcard(card)
        player receivs a card            
    """
    
    def __init__(self, name = "Player", money=1000):
        if(name == 'house'):
            raise   #TODO
        
        self.name = name
        self.money = money
        self.bet_amount = 0  
        self.hand = []
    
    def bet(self, amount):
        """ Player can bet some money, but not more than he has. """
        
        if(self.money < amount):            
            self.bet_amount = self.money
        else:
            self.bet_amount = amount
        self.money -= self.bet_amount
        return self.bet_amount
    
    def win(self, factor = 1.0):        
        """Arguments:
        
        factor -- in certain cases player wins bet amount multiplied by some factor
        """
        
        won = self.bet_amount * factor
        self.money += (self.bet_amount + won)
        self.bet_amount = 0
        return won
    
    def tie(self):
        tied = self.bet_amount
        self.money += self.bet_amount
        self.bet_amount = 0
        return tied
    
    def loose(self):
        lost = self.bet_amount
        self.bet_amount = 0        
        return lost
    
    def prepareforgame(self):
        self.hand = []
        self.bet_amount = 0
        
    def getcard(self, card):
        self.hand.append(card)
    
    def __eq__(self, other):        
        return self.name.lower() == other.name.lower()
    
    def toDict(self):
        #return jsonpickle.encode(self)
        return {'name': self.name, 'money': self.money, 'bet_amount': self.bet_amount, 'hand': [i.tonum() for i in self.hand]}

    def __repr__(self):            
        return "{0}\n{1}USD\n{2}".format(self.name, self.money, self.hand)
    
class PlayerBlackJack(Player):
    """Player of GameBlackJack
    
    Player's hand is evaluated by the rules of blackjack.

    Methods
    -------
    
    isbust(), 
    has21()
        player's hand can have special values of over 21 (bust) or 21 (blackjack)
    cardsvalue()
        player's hand is evaluated by the rules of blackjack
    cardsdiff()
        difference between value of player's hand and target value of 21                
    """
    
    def cardsvalue(self):
        """Returns hand value that is closest to 21 
        
        Since Aces can have a value of wither 1 or 11, they initially count as 11. 
        If the sum is over 21, Aces start counting as 1 until there is no more Aces left or the sum is under 21. 
        
        Values of Blackjack cards:
        hand 2 - 10 = face value
        hand J,Q,K = 10
        Ace = 1
        """
        
        cardsum = 0
        aces = 0
        for c in self.hand:
            cardval = c.getval()
            cardsum += cardval
            if(cardval == 1):   # Aces are internally represented as 1
                cardsum += 10   # Initially count all Aces as 11
                aces += 1
        while(aces > 0 and cardsum > GameBlackJack.NATURAL): # count Aces as 1 instead until the sum is under 21
            cardsum -= 10
            aces -= 1                            
        return cardsum
    
    def cardsdiff(self):                                    
        return GameBlackJack.NATURAL - self.cardsvalue()
    
    def has21(self):
        return self.cardsvalue() == GameBlackJack.NATURAL
    
    def isbust(self):
        return self.cardsvalue() > GameBlackJack.NATURAL

    def __repr__(self):            
        return "\n{0}\t[{1}USD]\t{2} = {3} [bet {4}USD]".format(self.name, self.money, self.hand, self.cardsvalue(), self.bet_amount)


class PlayerBlackJackHouse(PlayerBlackJack):
    """House in BlackJack is just another player
        
    House has unlimited money and always matches other players's bets.
    House always wins with factor = 1.0
    """
    
    def __init__(self):
        super().__init__()
        self.name = "house"
        self.money = 0    # "unlimited"

    def win(self, amount):
        self.money += amount
    
    def loose(self, lost):        
        self.money -= lost
    
    def tie(self):
        pass
    
    def __repr__(self):
        return "\nhouse\t[{0}USD]\t{1}".format(self.money, [c for c in self.hand if not c.facedown], self.cardsvalue())
