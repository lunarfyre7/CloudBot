from cloudbot import hook

import copy
import random
import pickle
from collections import OrderedDict
from sqlalchemy import Table, Column, String, Integer, PickleType
from sqlalchemy.sql import select
from cloudbot.util import database

playertable = Table(
    'texemon',
    database.metadata,
    Column('player_name', String),
    Column('player_object', PickleType)
)

#awesomely simple Bunch class! http://code.activestate.com/recipes/52308/
class Bunch:
    def __init__(self, **kwds):
        self.__dict__.update(kwds)
print("texemon loaded")
CONF = Bunch(
    atk_base = 0.05, #balence of how powerful pokemon are (inverse)
    lvl_bias = 01.1, #how much level effects power
    starter_lvl = 5, #try and guess what this does?
    starter_type = "fennekin",
    starter_balls = 5,
    starter_potion = 2,
    spawn_min_lvl = 1,
    spawn_max_lvl = 100,
    spawn_base_lvl = 10,
    spawn_range_base = 5,
    spawn_range_mult_bias = 0.80,

    #standard moves
    MOVE = [
        {'name': 'swipe',        'power': 20},
        {'name': 'slash',        'power': 25},
        {'name': 'watergun',     'power': 20, 'type': 'water'},
        {'name': 'ember',        'power': 20, 'type': 'fire'},
        {'name': 'grass blade',  'power': 20, 'type': 'plant'}
    ],
    #pokemon
    POKE = [
        {'name': 'fennekin',   'type': 'fire',   'hp': 10, 'atk': 4, 'speed': 4, 'level': 4, 'moves': ['swipe', 'ember']},
        {'name': 'meowth',     'type': 'normal', 'hp': 10, 'atk': 3, 'speed': 5, 'level': 2, 'moves': ['swipe', 'slash']},
        {'name': 'squirtle',   'type': 'water',  'hp': 10, 'atk': 4, 'speed': 4, 'level': 4, 'moves': ['swipe', 'watergun']},
        {'name': 'bulbasaur',  'type': 'plant',  'hp': 12, 'atk': 4, 'speed': 3, 'level': 4, 'moves': ['swipe', 'grass blade']}
    ]
)
enabledChans = []

class Inp:
    """input wrapper helper thingy"""
    userStates = {}
    def __init__(self, msg=''):
        self.callbacks = OrderedDict()
        self.choice = None
        self.message = msg
        
    def add(self, arg):#decorator to add callback
        def register(func):
            self.callbacks[name] = func
            return func
        if callable(arg): #function
            name = arg.__name__
            return register(arg)
        else:#name arg
            name = arg
            return register
        
    def ask(self, nick):#ask for user input
        names = [ k for k, v in self.callbacks.items()]
        #names.sort()
        choices = range(len(names))
        msg = self.message + " " + ', '.join(["{}: {}".format(i+1,n) for i,n in enumerate(names)])#get list of names and apply indexes to them and join them into a string
        def get():
            inp = input(msg+" >>")
            try:
                inp = int(inp)-1
            except ValueError:
                print('invalid choice')
                return get()
            if inp not in choices:
                print('invalid choice')
                return get()
            return inp
        inp = get()
        self.callbacks[names[inp]]()#call it  
        
    def do(self, param, nick): #act on user input
        names = [ k for k, v in self.callbacks.items()]
        
        if param in names:
            return self.callbacks[param]()
        else:
            return "Invalid. Use [{}] here instead".format(', '.join(names))

class TypesMixin:
    """calculates the effectiveness of one type vs another"""
    table = {
        #'normal':   {},
        'fire':     {'water': 0.5, 'plant': 2,   'fire': 0.5},
        'water':    {'water': 0.5, 'plant': 0.5, 'fire': 2},
        'plant':    {'water': 2,   'plant': 0.5, 'fire': 0.5},
    }
    def typeCheck(self, target):
        """calc effectiveness of self vs target"""
        if self.type in self.table and target.type in self.table[self.type]:
            return self.table[self.type][target.type]
        else:
            return 1

class Move(TypesMixin):
    """
    name: name of move
    power: multiplier ususally from 1-100
    type: move type
    """
    def __init__(self, name, power, type='normal', moveType = "attack"):
        self.name = name
        self.power = power
        self.type = type
        self.moveType = moveType
    
    def effectiveness(self, target):
        """Returns the effectiveness this move will have on target based on power and type. Does not take into account pokemon level."""
        base = (self.power/100)/CONF.atk_base
        return base * super().typeCheck(target)
        
class Pokemon:
    
    def __init__(self, name, type, hp, level, speed, atk, moves=[], wild=True, template=False):
        self.name = name
        self.type = type #normal, fire, water, plant, etc
        self.hp = hp
        self.maxHP = hp
        self.level = level
        self.moves = moves #list of moves
        self.speed = speed
        self.atk = atk
        self.active = False #used by player object, true if in poke inventory
        self.wild = wild
        self.fainted = False #true if defeated
        
        if template:
            for k, v in template:
                self.__dict__[k] = v
    
    def copy(self):
        return copy.copy(self)
        
    def check(self):
        if self.hp <= 0:
            self.fainted = True
            return colored("{} has fainted!\n".format(self.name), 'yellow')
        return ''
    
    def potion(self, player):
        """uses potion from player to heal"""
        if player.bag['potion']:
            self.hp = self.maxHP
            player.bag['potion'] -= 1
            return True
        else:
            return False
            
    def fight(self, enemy, attack):
        """interface for attacking and being attacked based on lvl and speed"""
        if enemy.speed*(enemy.level*CONF.lvl_bias) < self.speed*(enemy.level*CONF.lvl_bias):
            cprint(self.attack(enemy, attack), 'green')
            cprint(enemy.attack(self, attack), 'red')
        else:
            cprint(enemy.attack(self, attack), 'red')
            cprint(self.attack(enemy, attack), 'green')
            
        #print(msg)

    def attack(self, target, move):
        #TODO: add move type diff stuff here...
        #get move. by index or name, then put it in `move` replacing the key...
        text = ''
        if self.fainted:
            return colored('{} is fainted and cannot battle'.format(self.name), 'yellow')
        if type(move) is str:
            for i, v in enumerate(self.moves):
                if v.name.lower() == move.lower():
                    move = v
                    break
        else:
            move = self.moves[move]
        assert type(move) is Move, "Move {} not found".format(move)
        
        #damage calc and handling
        #lvldiff = ((me.power/target.power)*CONF.lvl_bias + 1)/1+conf.lvl_bias#alt lvl calc formula
        damage = (self.level / target.level) * CONF.lvl_bias * move.effectiveness(target)
        target.hp -= damage
        text += "{} used {} on {}\n".format(self.name, move.name, target.name)
        if move.typeCheck(target) > 1:
            text += colored("It was super effective!\n", 'yellow')
        elif move.typeCheck(target) < 1:
            text += colored("It wasn't very effective\n", 'yellow')
        text += "Damage: {}, {}'s hp: {:0.2f}\n".format(damage, target.name, target.hp)
        text += target.check()
        
        #exp handling and check
        if target.fainted:
            exp = (target.level / self.level) * (target.level * CONF.lvl_bias)
            self.level += exp
            text += "+{:0.2f} EXP! level is now {:0.2f}\n".format(exp, self.level)
        return text

class Player:
    #class Poke:
        #"""storage type for holding pokemon in inventory"""
        #def __init__(self, pokemon):
            #self.pokemon = pokemon
            #self.active = False #true if in inventory
            
    def __init__(self):
        #self._inv = [] #inventory
        self._selected = None
        self.storage = [] #holds unused pokemon
        self.bag = {
            'pokeballs': CONF.starter_balls,
            'potions': CONF.starter_potion
            }
        starter = POKE[CONF.starter_type].copy()
        print(starter)
        self.addToInv(starter)
    def getInv(self):
        print(self.storage)
        inv = list(filter(lambda p: p.active ,self.storage)) #find pokemon marked as being in inv 
        assert len(inv) <=6 #because
        return inv 
    
    def addToInv(self, poke, index=-1):
        """Add pokemon from storage to inventory, or add new pokemon to player's inventory.
        If index != -1 then poke at position will be replaced and left in storage"""
        #poke = Player.Poke(poke)#make a container
        if poke not in self.storage:
            self.storage.append(poke)#add it to storage
        inv = self.getInv()
        if index in range(0, 5):
            inv[index].active = False
            poke.active = True
        elif len(inv) in range(0, 5):
            poke.active = True
            
    def healAll(self):
        for p in self.storage:
            p.hp = p.maxHP
    
    def catch(self, pokemon):
        """catch a pokemon, with a calculated chance of failure. returns true if caught"""
        if not pokemon.wild:
            return false #don't steal pokemon from other players
        ratio = pokemon.hp/pokemon.maxHP
        chance = 1/(ratio + pokemon.level/10)
        rand = random.uniform(0,1)
        if chance < rand:
            self.addToInv(pokemon)
            return True
        else: 
            return False

def init_conf():#init objects based on config
    global POKE, MOVE
    POKE = {}
    MOVE = {}
    for v in CONF.MOVE:
        MOVE[v['name']] = Move(**v)
    for v in CONF.POKE:
        moves = []
        for m in v['moves']:#buld moves
            moves.append(copy.copy(MOVE[m]))
        v['moves'] = moves #replace name list with move objects
        POKE[v['name']] = Pokemon(**v)

def save():
    with open("textemon.pickle", "wb") as f:
        pickle.dump(dat, f, pickle.HIGHEST_PROTOCOL)
    
def load():
    """load save file"""
    dat = None
    try:
        with open('textemon.pickle', 'rb') as f:
            dat = pickle.load(f)
    except FileNotFoundError:
        pass
    return dat

        
def battle_loop(enemy, player):
    playerPoke = player._selected
    #pdb.set_trace()
    print("{}(lvl{:0.2f}) vs opposing {}(lvl{:0.2f})".format(playerPoke.name, playerPoke.level, enemy.name, enemy.level))
    ended = False
    while not(enemy.fainted or playerPoke.fainted or ended):
        inp = Inp()
        
        @inp.add
        def Attack():
            moves = ', '.join(["({}) {}".format(i+1, v.name) for i, v in enumerate(playerPoke.moves)])#create a string for the list of moves
            i = int(input("Pick a move:\n{}\n>".format(moves)))
            if not (i >= 0 and i <= len(playerPoke.moves)): #catch out of bounds indexes
                print("Invalid input")
            else:
                i -= 1
                playerPoke.fight(enemy, i)
            
        @inp.add
        def Run():
            nonlocal ended #nonlocal, otherwise vars will be local withen the callback
            if(random.randint(0, 100) < 95):#chance of not escaping
                ended = True
                print("Got away")
            else:
                print("You couldn't get away")
                enemy.attack(player)
                
        @inp.add
        def Pokeball():
            nonlocal ended
            if player.catch(enemy):
                ended = True
                cprint("Got it!", 'green')
            else:
                cprint("Couldn't catch it", 'yellow')
        @inp.add
        def Info():
            pass
        
        @inp.add
        def Switch():
            pass
        
        @inp.add
        def Bag():
            pass
        
        inp.ask()

def settings():
    pass

def select(player):
    inv = player.getInv()
    plist = ["Active Pokemon:"]
    inp = Inp("Active Pokemon")
    for i, x in zip(range(0, len(inv)), inv):
        plist.append("({}) {} [hp:{}/{}, lvl:{}] [{}]".format(i, x.name, x.hp, x.maxHP, x.level, ", ".join([m.name for m in x.moves])))
        #@inp.add
        
    pstr = '\n'.join(plist)
    print(pstr)
    inp = input(">")
    if inp == 'q' or not int(inp) in range(0, len(inv)): return #just exit if wrong input is entered
    selected = inv[int(inp)]
    print("{} selected. [(0) Move to Poke inventory, (1) Store, (q) Quit menu]". format(selected.name))
    inp = input('>')
    if inp == '0':
        player._selected = selected
    elif inp == '1':
        selected.active = False

def spawn():
    """generate a random pokemon"""
    p = POKE[random.choice(list(POKE))].copy()#make a copy of a random pokemon form POKE
    _min = conf.spawn_min_lvl
    _max = conf.spawn_max_lvl
    difficulty = dat['difficulty']
    _range = conf.spawn_range_base * difficulty * conf.spawn_range_mult_bias
    base = difficulty * conf.spawn_range_mult_bias * conf.spawn_base_lvl
    
    a = base-(_range/2)
    b = base+(_range/2) 
    p.level = random.triangular(a, b)
    return p

def main():
    init_conf()
    
    #player = {
        #'pokemon': [starterPoke],
        #'selected_pokemon': 0
    #}
    player = Player()
    ##starter setup##
    starter = POKE[conf.starter_type].copy()
    player.addToInv(starter)
    player._selected = player.getInv()[0]
    print("Welcome to Textemon!\n\n")
    #user loop
    while 1:
        #print("What would you like to do?",
              #"[Encounter, SElect, List, LOad, SAve, SeTtings, Quit]")
        #inp = input(">")
        #test = lambda a, b: a.lower() == inp.lower() or b.lower() == inp.lower() #little helper function for comparing input choices
        inp = Inp("What would you like to do?")
        
        @inp.add
        def Encounter():
            wildpoke = spawn()
            print("A wild {} has appeared!".format(wildpoke.name))
            battle_loop(wildpoke, player)

        @inp.add
        def Select():
            select(player)

        @inp.add
        def Load():
            data = load()
            if data:
                global dat
                dat = data
                player = dat['player']
                print("Game loaded!")
            else:
                print("No save found")

        @inp.add
        def List():
            plist = ["\nselected pokemon:"]
            inv = player.getInv()
            for i, x in zip(range(0, len(inv)), inv):
                plist.append("({}) {} [hp:{}/{}, lvl:{}] [{}]".format(i, x.pokemon.name, x.pokemon.hp, x.pokemon.maxHP, x.pokemon.level, ", ".join([m.name for m in x.pokemon.moves])))
            plist.append('\nall pokemon:')
            for i, x in zip(range(0, len(player.storage)), player.storage):
                plist.append("({}) {} [hp:{}/{}, lvl:{}] [{}]".format(i, x.pokemon.name, x.pokemon.hp, x.pokemon.maxHP, x.pokemon.level, ", ".join([m.name for m in x.pokemon.moves])))
            print('\n'.join(plist))

        @inp.add 
        def Save():
            dat['player'] = player
            save()
            print("Game saved!")
            
        @inp.add 
        def Settings():
            settings()
            
        @inp.add 
        def Quit():
            sys.exit(0)

        inp.ask()
        #print("\n"*2, "*"*30, "\n"*1)#seperator
        print("*"*30, '\n')#seperator
        
def getPlayer(nick, db):
    s = playertable.select().where(playertable.c.player_name == nick)
    res = db.execute(s).fetchone()
    if res:
        return res['player_object']
    else:
        return False

def newPlayer(nick, db):
    """create a new player if none with nick exist"""
    if not getPlayer(nick, db):
        player = Player()
        i = playertable.insert().values(player_name=nick, player_object = player)
        db.execute(i)
        db.commit()
        return True
    else:
        return False
def savePlayer(nick, player, db):
    isnew = newPlayer(nick, db)
    q = playertable.update().\
        where(playertable.c.player_name == nick).\
        values(player_object = player)
    db.execute(q)
    db.commit()
    
@hook.on_start
def startup():
    init_conf()

@hook.command('tt', autohelp=False)
def texetest(text, chan):
    """texemon debugging"""
    return CONF

@hook.command('poke', 'texe', autohelp=False)
def texeinput(text, chan, nick, reply, notice, db):
    """main input command for texemon"""
    args = str.split(text)
    if len(args) > 0:
        inp = Inp()
        @inp.add
        def enable():
            if not chan in enabledChans:
                enabledChans.append(chan)
                return "Texemon enabled for {}".format(chan)
            else:
                return "Texemon already enabled for {}".format(chan)
        @inp.add
        def disable():
            if chan in enabledChans:
                enabledChans.remove(chan)
                return "Texemon disabled for {}".format(chan)
            else:
                return "Texemon is not enabled, nothing to disable {}".format(chan)
        @inp.add
        def stats():
            player = getPlayer(nick, db)
            inv = player.getInv()
            message = []
            for pokemon in inv:
                message.append('blah')
            message = ', '.join(message)
            notice(message)
        @inp.add 
        def reset():
            """reset player"""
            newPlayer = Player()
            savePlayer(nick, newPlayer, db)
            return "All player data reset for {}".format(nick)
        
        message = inp.do(args[0], nick)
        if message: reply(message)
    else:
        return "Texemon, text based pokemon clone. <irc interface/port not completed yet>"
