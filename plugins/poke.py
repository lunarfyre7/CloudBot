from cloudbot import hook
import random, inspect, pprint

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
