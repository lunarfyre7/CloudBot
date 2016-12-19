from cloudbot import hook
from cloudbot.event import EventType
import random, inspect, pprint
import pdb

"""
A collaction of random things lumped together in a glob of lines of mew.
"""

waitingForList = False

@hook.command
def poke(text, action):
    action("pokes {}".format(text))
    
@hook.command
def meow(text, action):
    if text:
        return "=^..^=<{{{}}}".format(text)
    else:
        action(random.choice(['meows', 'mews', 'mewos', 'nyas~', 'goes mew, mew, mew, mew', 'MEOWS']))
        
@hook.command
def dumpapi(conn, bot):
    pp = pprint.PrettyPrinter(indent=4)
    pp.pprint(inspect.getmembers(bot.connections['freenode']))
    print(conn.name)
    return "check console..."

def get_user_list(chan, conn, callback):
    global waitingForList
    waitingForList = [chan, callback]
    conn.cmd('names',chan)

@hook.event(EventType.other)
def event_handler(event, conn):
    global waitingForList
    if waitingForList:
        waitingForList[1](waitingForList[0], event)
        waitingForList = False

@hook.command
def listusers(chan, conn, has_permission):
    if not has_permission('botcontrol'):
        return "Hey, no spamming you! Only lunar can do that!"
    else:
        get_user_list(chan, conn, lambda channel, event: conn.message(channel, 'users: '+', '.join(event.content.lower().split())))

@hook.command('pdb', permissions=['botcontrol'])
def debug(bot,conn,chan,nick,reply):
    reply("triggering pdb, bot may freeze")
    pdb.set_trace()

@hook.command(permissions=['botcontrol'])
def amsg(bot, text):
    """Sends a message across all channels"""
    for conn in bot.connections.values():
        for chan in conn.channels:
            conn.message(chan, "GLOBAL: "+text)

@hook.command(autohelp = False)
def tarot():
    """Draws a random tarot card"""
    cards = [
        'the fool',
        'the magician',
        'the high priestess',
        'the empress',
        'the emperor',
        'the hierophant',
        'the lovers',
        'the chariot',
        'justice',
        'the hermit',
        'wheel of fortune',
        'strength',
        'the hanged man',
        'death',
        'temperance',
        'the devil',
        'the tower',
        'the star',
        'the moon',
        'the sun',
        'judgement',
        'the world'
        ]
    for s in ['wands','pentacles','cups','swords']:
        for i in range(2,11):
            cards.append('{} of {}'.format(i, s))
        for i in ['ace','page','knight','queen','king']:
            cards.append('{} of {}'.format(i, s))
    card = random.choice(cards)
    if random.random()>=0.5:
        card += ' rx'
    return card.title()
