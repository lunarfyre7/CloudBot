from cloudbot import hook
import random

@hook.command
def poke(text, action):
    action("pokes {}".format(text))
    
@hook.command
def meow(text, action):
    if text:
        return "=^..^=<{{{}}}".format(text)
    else:
        action(random.choice(['meows', 'mews', 'mewos', 'nyas~', 'goes mew, mew, mew, mew', 'MEOWS']))
