from cloudbot import hook

import copy, random, pickle, string
from collections import OrderedDict, defaultdict
from sqlalchemy import Table, Column, String, Integer, PickleType
from sqlalchemy.sql import select
from cloudbot.util import database

cprint = print #hack, TODO: change cprint code 

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
    difficulty = 1,

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
battleStates = []

def randomword(length):
   return ''.join(random.choice(string.ascii_lowercase) for i in range(length))

class Inp:
    """Input manager helper class"""
    userStates = defaultdict(lambda: [])
    def __init__(self, msg=''):
        self.callbacks = OrderedDict()
        self.choice = None
        self.message = msg
        self.nopop = False
        self.passInput = False
        
    def add(self, *args, **kwargs):#decorator to add callback
        #note, args changed to make adding named params easier
        arg = args[0] if len(args)>0 else False
        def register(func):
            self.callbacks[name] = func
            return func
        if callable(arg): #function
            name = arg.__name__
            return register(arg)
        elif type(arg) is str:#name arg
            name = arg
            return register
        
    def getList(self):
        """return a list of options"""
        return [ k for k, v in self.callbacks.items()]
    
    def pushState(self, nick):
        """add state for nick"""
        print("pushed "+nick)
        self.userStates[nick].append(copy.deepcopy(self))
        
    def popState(self, nick):
        """remove state for user"""
        if self.nopop:
            print("skipped popping "+nick)
            return self.getState(nick)
        print("popped "+nick)
        return self.userStates[nick].pop()
        
    def getState(self, nick):
        """get current deepest state for nick"""
        return self.userStates[nick][-1] if len(self.userStates[nick]) >0 else False
        
    def ask(self, nick):
        """prompt user for input"""
        self.pushState(nick)
        names = self.getList()
        choices = range(len(names))
        msg = self.message + ": " + ', '.join(["{}: {}".format(i+1,n) for i,n in enumerate(names)])+ ". Reply with .texe c <number>"#get list of names and apply indexes to them and join them into a string
        return(msg)
    
    def prompt(self, nick):
        """Decorator. Prompt user and return response to callback"""
        def wrapper(func):
            self.callbacks[len(self.callbacks)+1] = func #push into dict with a random name 
            self.passInput = True
            self.pushState(nick)
            return func
        return wrapper
        
    def choose(self,inp,nick,notice):
        """callback for handling reply to ask()"""
        if self.getState(nick):
            self = self.getState(nick)#restore old state
        else: 
            return "No open prompt"

        names = self.getList()
        choices = range(len(names))
        if self.passInput:#override to give input to last callback (used in prompt mode)
            key = next(reversed(self.callbacks))#last ordered dict key
            return self.callbacks[key](inp)
        def get():
            nonlocal inp
            try:
                inp = int(inp)-1
            except ValueError:
                notice('invalid choice')
                return get()
            if inp not in choices:
                notice('invalid choice, valid choices: '+', '.join(choices))
                return
            return inp
        inp = get()
        self.popState(nick)
        return self.callbacks[names[inp]]()#call it 
        
    def do(self, param, nick):
        """act on user input"""
        names = self.getList()
        
        if param in names:
            return self.callbacks[param]()
        else:
            return "Invalid. Valid args: {}".format(', '.join(names))

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
    
    def getInfoString(self):
        return "{n}: hp:{hp}/{mhp}, lvl: {lvl}".format(n=self.name, hp=self.hp, mhp=self.maxHP, lvl=self.level)
        
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
            
    def fight(self, enemy, attack, r):
        """interface for attacking and being attacked based on lvl and speed"""
        if enemy.speed*(enemy.level*CONF.lvl_bias) < self.speed*(enemy.level*CONF.lvl_bias):
            r(self.attack(enemy, attack))
            r(enemy.attack(self, attack))
        else:
            r(enemy.attack(self, attack))
            r(self.attack(enemy, attack))
            
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
            
    def __init__(self, name):
        #self._inv = [] #inventory
        self.name = name
        self.storage = [] #holds unused pokemon
        self.bag = {
            'pokeballs': CONF.starter_balls,
            'potions': CONF.starter_potion
            }
        starter = POKE[CONF.starter_type].copy()
        print(starter)
        self.addToInv(starter)
        self._selected = starter
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

        
def battle_loop(enemy, player, reply):
    """enemy (pokemon) vs player"""
    playerPoke = player._selected
    #pdb.set_trace()
    ended = False

    inp = Inp("{}(lvl{:0.2f}) vs opposing {}(lvl{:0.2f})".format(playerPoke.name, playerPoke.level, enemy.name, enemy.level))
    
    @inp.add
    def Attack():
        moves = ', '.join(["({}) {}".format(i+1, v.name) for i, v in enumerate(playerPoke.moves)])#create a string for the list of moves
        #i = int(input("Pick a move:{}>".format(moves)))
        inp.nopop = True #disable poping state for this loop
        reply("[layer 1]"+moves)
        p = Inp()
        @p.prompt(player.name)
        def prompt(i):
            reply('[layer 2]')
            i = int(i)
            if not (i >= 0 and i <= len(playerPoke.moves)): #catch out of bounds indexes
                reply("Invalid input")
                inp.ask(player.name)
            else:
                i -= 1
                playerPoke.fight(enemy, i, r=reply)
                inp.ask(player.name)
    @inp.add
    def Run():
        nonlocal ended #nonlocal, otherwise vars will be local withen the callback
        if(random.randint(0, 100) < 95):#chance of not escaping
            ended = True
            reply("Got away")
        else:
            reply("You couldn't get away")
            enemy.attack(player)
            inp.ask(player.name)
    @inp.add
    def Pokeball():
        nonlocal ended
        if player.catch(enemy):
            ended = True
            reply("Got it!")
        else:
            reply("Couldn't catch it")
            inp.ask(player.name)
    @inp.add
    def Info():
        pass
    
    @inp.add
    def Switch():
        pass
    
    @inp.add
    def Bag():
        pass
    
    reply(inp.ask(player.name))

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
    #inp = input(">")
    if inp == 'q' or not int(inp) in range(0, len(inv)): return #just exit if wrong input is entered
    selected = inv[int(inp)]
    print("{} selected. [(0) Move to Poke inventory, (1) Store, (q) Quit menu]". format(selected.name))
    #inp = input('>')
    if inp == '0':
        player._selected = selected
    elif inp == '1':
        selected.active = False

def spawn():
    """generate a random pokemon"""
    p = POKE[random.choice(list(POKE))].copy()#make a copy of a random pokemon form POKE
    _min = CONF.spawn_min_lvl
    _max = CONF.spawn_max_lvl
    difficulty = CONF.difficulty
    _range = CONF.spawn_range_base * difficulty * CONF.spawn_range_mult_bias
    base = difficulty * CONF.spawn_range_mult_bias * CONF.spawn_base_lvl
    
    a = base-(_range/2)
    b = base+(_range/2) 
    p.level = random.triangular(a, b)
    return p

#def main():
    ##From old cli interface, doesn't do anything for irc. Only kept as a reference... TODO remove this.
    #init_conf()
    
    ##player = {
        ##'pokemon': [starterPoke],
        ##'selected_pokemon': 0
    ##}
    #player = Player()
    ###starter setup##
    #starter = POKE[CONF.starter_type].copy()
    #player.addToInv(starter)
    #player._selected = player.getInv()[0]
    #print("Welcome to Textemon!\n\n")
    ##user loop
    #while 1:
        ##print("What would you like to do?",
              ##"[Encounter, SElect, List, LOad, SAve, SeTtings, Quit]")
        ##inp = input(">")
        ##test = lambda a, b: a.lower() == inp.lower() or b.lower() == inp.lower() #little helper function for comparing input choices
        #inp = Inp("What would you like to do?")
        
        #@inp.add
        #def Encounter():
            #wildpoke = spawn()
            #print("A wild {} has appeared!".format(wildpoke.name))
            #battle_loop(wildpoke, player)

        #@inp.add
        #def Select():
            #select(player)

        #@inp.add
        #def Load():
            #data = load()
            #if data:
                #global dat
                #dat = data
                #player = dat['player']
                #print("Game loaded!")
            #else:
                #print("No save found")

        #@inp.add
        #def List():
            #plist = ["\nselected pokemon:"]
            #inv = player.getInv()
            #for i, x in zip(range(0, len(inv)), inv):
                #plist.append("({}) {} [hp:{}/{}, lvl:{}] [{}]".format(i, x.pokemon.name, x.pokemon.hp, x.pokemon.maxHP, x.pokemon.level, ", ".join([m.name for m in x.pokemon.moves])))
            #plist.append('\nall pokemon:')
            #for i, x in zip(range(0, len(player.storage)), player.storage):
                #plist.append("({}) {} [hp:{}/{}, lvl:{}] [{}]".format(i, x.pokemon.name, x.pokemon.hp, x.pokemon.maxHP, x.pokemon.level, ", ".join([m.name for m in x.pokemon.moves])))
            #print('\n'.join(plist))

        #@inp.add 
        #def Save():
            #dat['player'] = player
            #save()
            #print("Game saved!")
            
        #@inp.add 
        #def Settings():
            #settings()
            
        #@inp.add 
        #def Quit():
            #sys.exit(0)

        #inp.ask()
        ##print("\n"*2, "*"*30, "\n"*1)#seperator
        #print("*"*30, '\n')#seperator
        
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
        player = Player(nick)
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
def texetest(text, chan, notice, nick, reply, db):
    """texemon debugging"""
    inp = Inp('Inp.ask() test')
    args = str.split(text)
    @inp.add 
    def reset():
        """reset all your game data"""
        newPlayer = Player(nick)
        savePlayer(nick, newPlayer, db)
        return "All player data reset for {}, hope that's what you meant to do...".format(nick)
    @inp.add
    def triggerfight():
        player = getPlayer(args[1], db)
        pokemon = spawn()
        battle_loop(pokemon, player, reply)
    
    return inp.do(args[0], nick)

@hook.command('texe', 'pokemon', autohelp=False)
def texeinput(text, chan, nick, reply, notice, db):
    """main input command for texemon"""
    args = str.split(text)
    newPlayer(nick, db) #create a new player if none already
    player = getPlayer(nick, db)
    if len(args) > 0:
        inp = Inp()
        @inp.add
        def enable():
            """Enable wild pokemon spawning and chatter in channel"""
            if nick == chan:
                return "Use in a channel"
            elif not chan in enabledChans:
                enabledChans.append(chan)
                return "Texemon enabled in {}".format(chan)
            else:
                return "Texemon already enabled in {}".format(chan)
        @inp.add
        def disable():
            """Disable wild pokemon spawning and chatter in channel"""
            if nick == chan:
                return "Use in a channel"
            elif chan in enabledChans:
                enabledChans.remove(chan)
                return "Texemon disabled in {}".format(chan)
            else:
                return "Texemon is not enabled, nothing to disable in {}".format(chan)
        @inp.add
        def stats():
            """Display your stats"""
            inv = player.getInv()
            message = []
            for pokemon in inv:
                message.append(pokemon.getInfoString())
            message = ', '.join(message)
            notice(message)
        @inp.add
        def selection():
            select(player)
        @inp.add('c') 
        def choose(): #reply to a prompt
            return inp.choose(args[1],nick,reply)
            
        @inp.add
        def help():
            if len(args) > 1 and args[1] in inp.getList():#return docstring on supplied arg
                helptext = inp.callbacks[args[1]].__doc__
                if helptext:
                    notice(helptext)
                    return
            #default
            notice("argument list: {}. Try \".texe help arg\"".format(inp.getList()))
        message = inp.do(args[0], nick)
        if message: reply(message)
    else:
        return "Texemon, text based pokemon clone. Try \".texe help\""
